"""Шлюз к нейросети для класса.

Ключ поставщика хранится только на учительском ПК. Ученики спрашивают нейросеть через сервер курса:
вопрос встаёт в очередь, сервер отправляет вопросы поставщику строго по одному («один поток»),
а ученик видит своё место в очереди.

Поставщики:
  gigachat — GigaChat (Сбер): ключ авторизации → токен на 30 минут → запросы.
  openai   — любой сервис с OpenAI-совместимым API (в том числе локальная Ollama).
  offline  — запасной режим без сети: короткий заготовленный ответ.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

DEFAULT_CONFIG = {
    "provider": "gigachat",
    "mode": "live",                 # live — работает; offline — запасной режим; pause — нейросеть на паузе
    "manual_override": False,       # True, если учитель вручную задал провайдера/адрес
    # GigaChat
    "gigachat_key": "",             # «Ключ авторизации» из личного кабинета (секрет, наружу не отдаём)
    "gigachat_scope": "GIGACHAT_API_PERS",
    "gigachat_model": "GigaChat",
    "gigachat_oauth_url": "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
    "gigachat_api_url": "https://gigachat.devices.sberbank.ru/api/v1",
    "ca_file": "",                  # сертификат «Russian Trusted Root CA», если его нет в системе
    "verify_ssl": True,
    # OpenAI-совместимый сервис
    "openai_base_url": "",
    "openai_key": "",
    "openai_models": "",
    # ограничения для класса
    "max_tokens": 1500,             # запас токенов, чтобы ответы не обрезались на полуслове
    "max_prompt_chars": 2000,       # длина вопроса
    "min_interval": 1,              # секунд между вопросами одного ученика
    "daily_limit": 80,              # вопросов в день на ученика
    "short_hint": True,             # просить модель отвечать коротко
    "no_code": True,                # не писать ученикам готовый код (задания решают сами)
    "cache_minutes": 10,            # одинаковые «строгие» вопросы (temperature ≤ 0.3) отвечаем из памяти
}
SECRETS = ("gigachat_key", "openai_key")
URL_CONFIG_KEYS = ("openai_base_url", "gigachat_oauth_url", "gigachat_api_url")
SHORT_HINT = "Отвечай по-русски, кратко и по делу: максимум 2–3 предложения."
NO_CODE_HINT = (
    "Отвечай естественным языком — как грамотный, спокойный и дружелюбный наставник. "
    "Без клоунады, пафоса, сюсюканья и карикатурных выкриков. "
    "Если просят готовый код или решение учебной задачи — не давай готовый код целиком, а просто и понятно подскажи идею или наводящий шаг. "
    "Если в коде ошибка — спокойно и точно укажи, на что обратить внимание. "
    "Если задана роль — отвечай в её стиле, но сдержанно, органично и без кринжа."
)
ASKS_CODE = re.compile(r"(напиши|сделай|реши|дай|скинь|допиши|исправь)[^.?!]{0,40}(код|программ|скрипт|решени|задани)"
                       r"|python|питон|\bdef\b|print\(|input\(", re.I)
TICKET_STALE = 20       # секунд без опроса — ученик закрыл программу, вопрос убираем из очереди
PERSONAL = re.compile(r"(\+?\d[\d\-\s()]{8,}\d)|([\w.-]+@[\w-]+\.\w+)|(парол|адрес|телефон|паспорт)", re.I)
AI_PASTE_PATTERNS = re.compile(
    r"```(?:python|py)?|^```"
    r"|вот\s+(?:готовый\s+)?код"
    r"|вот\s+(?:полное\s+)?решение"
    r"|конечно[,!]?\s+вот"
    r"|держи\s+код"
    r"|надеюсь[,!]?\s+поможет"
    r"|here\s+is\s+(?:the\s+)?code"
    r"|as\s+an\s+ai",
    re.I | re.M
)


class AIError(Exception):
    """Ошибка, понятная ученику и учителю. retry_after — через сколько секунд можно повторить."""

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


def _validate_url(url: str, allow_empty: bool = False) -> str:
    u = str(url or "").strip()
    if not u:
        if allow_empty:
            return ""
        raise AIError("Не задан адрес сервиса нейросети")
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise AIError("Адрес сервиса должен начинаться с http:// или https://")
    return u


def _atomic_write_json(path: str, data: dict) -> None:
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Поставщики
# ---------------------------------------------------------------------------
def _ssl_context(cfg: dict) -> ssl.SSLContext:
    if not cfg.get("verify_ssl", True):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context()
    if cfg.get("ca_file"):
        ctx.load_verify_locations(cfg["ca_file"])
    return ctx


def _http(url: str, data: bytes | None, headers: dict, cfg: dict, timeout: int = 60) -> dict:
    url = _validate_url(url)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        ctx = _ssl_context(cfg) if url.startswith("https://") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read().decode("utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise AIError("поставщик вернул неожиданный формат ответа")
            return parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        e.close()
        if e.code == 401:
            raise AIError("поставщик не принял ключ (401): проверьте ключ авторизации") from None
        if e.code == 429:
            raise AIError("поставщик просит подождать (429): слишком много запросов") from None
        if e.code == 402:
            raise AIError("закончились токены у поставщика (402)") from None
        raise AIError(f"поставщик ответил ошибкой {e.code}: {body}") from None
    except ssl.SSLError as e:
        raise AIError("не удалось проверить сертификат поставщика. Для GigaChat нужен сертификат "
                      "«Russian Trusted Root CA» (НУЦ Минцифры): укажите путь к нему в настройках") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError):
            raise AIError("не удалось проверить сертификат поставщика. Для GigaChat нужен сертификат "
                          "«Russian Trusted Root CA» (НУЦ Минцифры): укажите путь к нему в настройках") from e
        raise AIError(f"нет связи с поставщиком: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise AIError(f"поставщик не ответил вовремя: {e}") from e
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        raise AIError(f"поставщик вернул некорректный JSON: {e}") from None
    except UnicodeEncodeError:
        raise AIError("в ключе есть недопустимые символы: скопируйте ключ из личного кабинета ещё раз") from None


def to_gigachat(messages: list) -> list:
    """Переписка в формате OpenAI (tool_calls, роль tool) → формат GigaChat (function_call, роль function)."""
    out, names = [], {}
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            call = m["tool_calls"][0]                 # GigaChat за один шаг вызывает одну функцию
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            names[call.get("id")] = fn.get("name")
            msg = {"role": "assistant", "content": m.get("content") or "",
                   "function_call": {"name": fn.get("name"), "arguments": args if isinstance(args, dict) else {}}}
            if call.get("id") and call["id"] != "call_1":
                msg["functions_state_id"] = call["id"]
            out.append(msg)
        elif role == "tool":
            content = str(m.get("content") or "")
            try:
                ok = isinstance(json.loads(content), dict)
            except ValueError:
                ok = False
            # результат функции GigaChat принимает только как JSON-объект
            out.append({"role": "function", "name": names.get(m.get("tool_call_id")) or m.get("name") or "tool",
                        "content": content if ok else json.dumps({"result": content}, ensure_ascii=False)})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


class GigaChat:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.token = ""
        self.expires = 0.0
        self.key_hash = ""

    def _auth(self, cfg: dict) -> str:
        key = cfg.get("gigachat_key", "").strip()
        if not key:
            raise AIError("не задан ключ авторизации GigaChat (пульт учителя → Нейросеть → Настройки)")
        h = hashlib.sha256(key.encode()).hexdigest()
        with self._lock:
            if self.token and self.key_hash == h and time.time() < self.expires - 60:
                return self.token
            r = _http(cfg["gigachat_oauth_url"], f"scope={cfg['gigachat_scope']}".encode(),
                      {"Authorization": "Basic " + key, "RqUID": str(uuid.uuid4()),
                       "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, cfg, timeout=20)
            token = r.get("access_token")
            if not isinstance(token, str) or not token:
                raise AIError("поставщик не вернул токен доступа")
            self.token = token
            try:
                exp = float(r.get("expires_at", 0))
            except (TypeError, ValueError):
                exp = 0.0
            self.expires = exp / 1000 if exp > 1e11 else (exp or time.time() + 25 * 60)
            self.key_hash = h
            return self.token

    def chat(self, cfg: dict, messages: list, temperature: float, max_tokens: int, tools=None) -> dict:
        token = self._auth(cfg)
        body = {"model": cfg["gigachat_model"], "messages": to_gigachat(messages),
                "temperature": max(0.01, float(temperature)), "max_tokens": int(max_tokens)}
        if tools:
            # GigaChat описывает инструменты как functions (старый формат OpenAI)
            body["functions"] = [t["function"] for t in tools if isinstance(t, dict) and t.get("type") == "function"]
            body["function_call"] = "auto"
        r = _http(cfg["gigachat_api_url"].rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                  {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"}, cfg)
        try:
            msg = r["choices"][0]["message"]
            if not isinstance(msg, dict):
                raise TypeError("message is not dict")
        except (KeyError, IndexError, TypeError):
            raise AIError("поставщик вернул неожиданный формат ответа") from None
        out: dict = {"content": msg.get("content")}
        fc = msg.get("function_call")
        if isinstance(fc, dict):
            args = fc.get("arguments")
            out["tool_calls"] = [{"id": msg.get("functions_state_id") or "call_1", "type": "function",
                                  "function": {"name": fc.get("name"), "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}}]
            out["content"] = None if not out["content"] else out["content"]
        return out


class OpenAICompatible:
    def chat(self, cfg: dict, messages: list, temperature: float, max_tokens: int, tools=None) -> dict:
        base = cfg.get("openai_base_url", "").rstrip("/")
        models = [m.strip() for m in cfg.get("openai_models", "").split(",") if m.strip()]
        if not base or not models:
            raise AIError("не заданы адрес сервиса и модели (пульт учителя → Нейросеть → Настройки)")
        last: AIError | None = None
        for model in models:
            body = {"model": model, "messages": messages, "temperature": float(temperature),
                    "max_tokens": max(256, int(max_tokens))}
            if tools:
                body["tools"] = tools
            try:
                r = _http(base + "/chat/completions", json.dumps(body).encode(),
                          {"Authorization": "Bearer " + cfg.get("openai_key", ""), "Content-Type": "application/json"}, cfg)
                try:
                    ch = r["choices"][0]
                    msg = ch["message"]
                    if not isinstance(ch, dict) or not isinstance(msg, dict):
                        raise TypeError("choice/message is not dict")
                except (KeyError, IndexError, TypeError):
                    raise AIError("поставщик вернул неожиданный формат ответа") from None
                content = msg.get("content")
                if ch.get("finish_reason") == "length" and not msg.get("tool_calls") and len((content or "").strip()) < 2:
                    last = AIError(f"модель {model} обрезала ответ")
                    continue
                if content or msg.get("tool_calls"):
                    return {"content": content, "tool_calls": msg.get("tool_calls")}
            except AIError as e:
                last = e
        raise last or AIError("модели вернули пустой ответ")


def offline_answer(messages: list) -> dict:
    q = next((m.get("content", "") for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user"), "")
    q = (q or "").strip().replace("\n", " ")
    return {"content": f"🤖 (Запасной режим: нейросеть сейчас отдыхает.) Я получил вопрос «{q[:60]}» и отвечу, когда учитель включит нейросеть."}


# ---------------------------------------------------------------------------
# Очередь
# ---------------------------------------------------------------------------
class Ticket:
    def __init__(self, tid: int, student_id, name: str, pc: str, messages: list, temperature: float, max_tokens: int, tools):
        self.id = tid
        self.student_id = student_id
        self.name = name
        self.pc = pc
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools
        self.created = time.time()
        self.polled = time.time()
        self.status = "queued"          # queued → working → done | error
        self.message = None
        self.error = ""
        self.cached = False
        self.logged = False


class Gateway:
    """Очередь вопросов к нейросети: параллельная обработка запросов класса с квотами и кэшем."""

    def __init__(self, data_dir: str, log_fn=None):
        self.path = os.path.join(data_dir, "ai.json")
        self.cfg = dict(DEFAULT_CONFIG)
        self.cfg.update(self._read())
        self.lock = threading.Condition()
        self.tickets: dict[int, Ticket] = {}
        self.next_id = 1
        self.active_students: set = set()
        self.active_tickets: dict[int, Ticket] = {}
        self.executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="kurs-ai")
        self.last_ok: float | None = None
        self.last_error = ""
        self.fails = 0
        self.durations: collections.deque[float] = collections.deque(maxlen=20)
        self.cache: dict[str, tuple[float, dict]] = {}
        self.last_ask: dict = {}
        self._ai_code_cache: dict[str, tuple[bool, str]] = {}
        self.log_fn = log_fn          # (ticket, ms) → запись в ленту учителя
        self.providers = {"gigachat": GigaChat(), "openai": OpenAICompatible()}
        self._last_bridge_check = 0.0
        self._bridge_info: dict | None = None
        self._stop_event = threading.Event()
        self._bridge_event = threading.Event()
        self._bridge_thread = threading.Thread(target=self._bridge_loop, name="kurs-ai-bridge", daemon=True)
        self._bridge_thread.start()
        self._bridge_event.set()

    def _bridge_loop(self) -> None:
        """Фоновая проверка доступности моста ИИ, не блокирующая HTTP-обработчики."""
        while not self._stop_event.is_set():
            self._bridge_event.wait(timeout=60.0)
            self._bridge_event.clear()
            if self._stop_event.is_set():
                break
            try:
                self._fetch_and_apply_bridge()
            except Exception:  # noqa: BLE001
                pass

    def trigger_bridge_check(self, force: bool = False) -> dict | None:
        """Возвращает кэшированный статус моста и при необходимости запускает фоновое обновление."""
        now = time.time()
        with self.lock:
            info = dict(self._bridge_info) if self._bridge_info else None
            need = force or (now - self._last_bridge_check >= 30.0)
        if need and not self._stop_event.is_set():
            self._bridge_event.set()
        return info

    def _fetch_and_apply_bridge(self) -> dict | None:
        """Сетевая проверка моста ИИ и применение к self.cfg (без перезаписи ручных настроек учителя)."""
        now = time.time()
        with self.lock:
            self._last_bridge_check = now
            if self.cfg.get("manual_override") or (self.cfg.get("provider") == "gigachat" and self.cfg.get("gigachat_key")):
                self._bridge_info = None
                return None

        # 0. Проверяем локальный Antigravity Tools (если сервер запущен на этом же компьютере)
        local_direct = False
        try:
            req_local = urllib.request.Request(
                "http://127.0.0.1:8045/v1/models",
                headers={"Authorization": "Bearer sk-class-b75732a69115bc0c7436a9b561db217509ec0de18069d43d"},
            )
            with urllib.request.urlopen(req_local, timeout=0.6) as r:
                if r.status == 200:
                    local_direct = True
        except Exception:  # noqa: BLE001
            pass

        bridge = None
        if local_direct:
            bridge = {
                "enabled": True,
                "openai_base_url": "http://127.0.0.1:8045/v1",
                "openai_key": "sk-class-b75732a69115bc0c7436a9b561db217509ec0de18069d43d",
                "openai_models": "gemini-3.8-flash-low,gemini-3.5-flash-lite,gemini-3.8-flash,claude-sonnet-4-6",
                "updated_at": now,
            }
        else:
            # 1. Локальный файл из репозитория курса
            bridge_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_bridge.json")
            if os.path.isfile(bridge_file):
                try:
                    with open(bridge_file, encoding="utf-8") as fh:
                        d = json.load(fh)
                        if isinstance(d, dict) and d.get("enabled") and d.get("openai_base_url"):
                            bridge = d
                except (OSError, ValueError):
                    pass

            # 2. Попытка запросить свежий адрес из GitHub (если git pull на учительском ПК ещё не делали)
            try:
                url = "https://raw.githubusercontent.com/qwerty-ll/chatbots-kurs/main/kurs/server/ai_bridge.json"
                req = urllib.request.Request(url, headers={"User-Agent": "kurs-server", "Cache-Control": "no-cache"})
                with urllib.request.urlopen(req, timeout=2.5) as r:
                    d = json.loads(r.read().decode("utf-8"))
                    if isinstance(d, dict) and d.get("enabled") and d.get("openai_base_url"):
                        if not bridge or d.get("updated_at", 0) >= bridge.get("updated_at", 0):
                            bridge = d
            except Exception:  # noqa: BLE001
                pass

        with self.lock:
            self._last_bridge_check = time.time()
            # Повторно проверяем под замком: учитель мог поменять настройки во время сетевого запроса
            if self.cfg.get("manual_override") or (self.cfg.get("provider") == "gigachat" and self.cfg.get("gigachat_key")):
                self._bridge_info = None
                return None
            if bridge and bridge.get("enabled"):
                try:
                    b_url = _validate_url(bridge["openai_base_url"])
                except AIError:
                    self._bridge_info = None
                    return None
                self.cfg["provider"] = "openai"
                self.cfg["openai_base_url"] = b_url
                self.cfg["openai_key"] = str(bridge.get("openai_key", ""))
                self.cfg["openai_models"] = str(bridge.get("openai_models", "gemini-3.8-flash-low,gemini-3.5-flash-lite,gemini-3.8-flash"))
                # Не сбрасываем ручные режимы pause / offline
                if self.cfg.get("mode") not in ("pause", "offline"):
                    self.cfg["mode"] = "live"
                self._bridge_info = {
                    "active": True,
                    "url": b_url,
                    "models": self.cfg["openai_models"],
                    "updated_at": bridge.get("updated_at", 0),
                }
                return dict(self._bridge_info)
            self._bridge_info = None
            return None

    def check_bridge(self, force_fetch: bool = False) -> dict | None:
        """Проверяет наличие активного туннеля моста ИИ (ai_bridge.json или GitHub).
        Если force_fetch=False — не блокирует HTTP-поток, возвращая кэш и запуская фоновое обновление.
        """
        if not force_fetch:
            return self.trigger_bridge_check(force=False)
        return self._fetch_and_apply_bridge()

    def check_ai_code(self, text: str) -> tuple[bool, str]:
        """Определяет с помощью ИИ на учительском ПК, является ли код решением нейросети.
        Возвращает (is_ai, reason).
        """
        if not text or len(text.strip()) < 20:
            return False, "короткий фрагмент"

        cache_key = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        with self.lock:
            cached = self._ai_code_cache.get(cache_key)
        if cached is not None:
            return cached

        # 1. Быстрый regex-фильтр: явные фразы решений или разметка
        if AI_PASTE_PATTERNS.search(text):
            res = (True, "явная разметка/фразы нейросети")
            with self.lock:
                self._ai_code_cache[cache_key] = res
            return res

        self.trigger_bridge_check()
        with self.lock:
            if not self._configured_locked() or self.cfg.get("mode") == "pause":
                return False, "нейросеть не настроена"

        prompt = (
            "Ты — строгий школьный арбитр курса программирования Python.\n"
            "Определи, скопирован ли данный фрагмент кода из нейросети (ChatGPT, GigaChat, DeepSeek и др.) как готовое решение задачи.\n"
            "Маркеры ИИ: готовые законченные функции учебных задач, типовые комментарии на русском, академичный стиль решения.\n"
            "Маркеры ученика: 1-2 простые строки, опечатки, отдельные команды, черновик.\n\n"
            f"Код:\n```\n{text[:1200]}\n```\n\n"
            "Ответь строго одним словом: AI (если это готовое решение/код из ИИ) или OK (если обычный код)."
        )
        t = Ticket(0, None, "арбитр", "", [{"role": "user", "content": prompt}], 0.0, 10, None)
        try:
            msg = self._call(t)
            content = str(msg.get("content", "")).strip().upper()
            is_ai = "AI" in content
            reason = "ИИ подтвердил готовое решение" if is_ai else "обычный код"
            with self.lock:
                if len(self._ai_code_cache) > 500:
                    self._ai_code_cache.clear()
                self._ai_code_cache[cache_key] = (is_ai, reason)
            return is_ai, reason
        except Exception as e:  # noqa: BLE001
            return False, f"ошибка проверки: {e}"

    # --- настройки ---
    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                d = json.load(fh)
                return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_config(self, patch: dict) -> None:
        if not isinstance(patch, dict):
            raise AIError("Неверный формат настроек")
        with self.lock:
            updated = dict(self.cfg)
            for k, v in patch.items():
                if k not in DEFAULT_CONFIG:
                    continue
                if k in SECRETS and not v:
                    continue                    # пустое поле — ключ не меняем
                default = DEFAULT_CONFIG[k]
                if isinstance(default, bool):
                    v = bool(v)
                elif isinstance(default, int):
                    try:
                        v = int(v)
                    except (TypeError, ValueError):
                        raise AIError(f"Параметр {k} должен быть целым числом") from None
                else:
                    v = str(v).strip()
                if k in URL_CONFIG_KEYS:
                    v = _validate_url(v, allow_empty=True)
                updated[k] = v

            # Отслеживаем ручную настройку учителя, чтобы мост не перезатирал её
            if "manual_override" not in patch:
                if "provider" in patch and updated.get("provider") == "gigachat":
                    updated["manual_override"] = True
                elif "openai_base_url" in patch:
                    if updated.get("openai_base_url"):
                        bridge_url = (self._bridge_info or {}).get("url", "")
                        if updated["openai_base_url"] != bridge_url:
                            updated["manual_override"] = True
                    else:
                        updated["manual_override"] = False

            self.cfg = updated
            if self.cfg.get("manual_override"):
                self._bridge_info = None
            _atomic_write_json(self.path, self.cfg)
            self.fails = 0
            self.last_error = ""

    def public_config(self) -> dict:
        with self.lock:
            out = {k: v for k, v in self.cfg.items() if k not in SECRETS}
            out["has_gigachat_key"] = bool(self.cfg.get("gigachat_key"))
            out["has_openai_key"] = bool(self.cfg.get("openai_key"))
            return out

    # --- ученик ---
    def ask(self, student_id, name: str, pc: str, messages: list, temperature, max_tokens, tools, today_count: int, allow_code: bool = False) -> Ticket:
        with self.lock:
            cfg = dict(self.cfg)
        if cfg["mode"] == "pause":
            raise AIError("Учитель поставил нейросеть на паузу. Подожди немного.")
        if not isinstance(messages, list) or not messages:
            raise AIError("Пустой вопрос.")
        clean = []
        total = 0
        for m in messages[-30:]:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "user"))
            content = m.get("content")
            if role not in ("system", "user", "assistant", "tool", "function"):
                continue
            total += len(str(content or ""))
            item = {"role": role, "content": "" if content is None else str(content)}
            for k in ("tool_calls", "tool_call_id", "name"):
                if m.get(k):
                    item[k] = m[k]
            clean.append(item)
        if not clean:
            raise AIError("Пустой вопрос.")
        if total > cfg["max_prompt_chars"] * 4 or len(str(clean[-1]["content"])) > cfg["max_prompt_chars"]:
            raise AIError(f"Слишком длинный вопрос: не больше {cfg['max_prompt_chars']} символов.")
        if today_count >= cfg["daily_limit"]:
            raise AIError(f"На сегодня вопросы к нейросети закончились ({cfg['daily_limit']}). Продолжим на следующем занятии!")
        try:
            temperature = min(1.5, max(0.0, float(temperature)))
        except (TypeError, ValueError):
            temperature = 0.7
        try:
            max_tokens = min(int(cfg["max_tokens"]), max(16, int(max_tokens)))
        except (TypeError, ValueError):
            max_tokens = int(cfg["max_tokens"])
        hint = ""
        if not allow_code:
            hint = " ".join(h for h, on in ((SHORT_HINT, cfg["short_hint"]), (NO_CODE_HINT, cfg.get("no_code", True))) if on)
        if hint:
            if clean[0]["role"] == "system":
                clean[0]["content"] = (clean[0]["content"] + " " + hint).strip()
            else:
                clean.insert(0, {"role": "system", "content": hint})
        log_immediately = False
        with self.lock:
            now = time.time()
            self._gc()
            if self.cfg["mode"] == "pause":
                raise AIError("Учитель поставил нейросеть на паузу. Подожди немного.")
            if student_id is not None and student_id in self.active_students:
                raise AIError("Ты уже ждёшь ответа на прошлый вопрос.")
            wait = self.cfg["min_interval"] - (now - self.last_ask.get(student_id, 0))
            # результат инструмента — продолжение того же шага агента, его не задерживаем
            agent_step = clean[-1]["role"] in ("tool", "function")
            if student_id is not None and wait > 0 and not agent_step:
                raise AIError(f"Не так часто 🙂 Следующий вопрос — через {int(wait) + 1} с.", retry_after=int(wait) + 1)
            self.last_ask[student_id] = now
            t = Ticket(self.next_id, student_id, name, pc, clean, temperature, max_tokens, tools)
            self.next_id += 1
            self.tickets[t.id] = t
            key = self._cache_key_locked(t)
            hit = self.cache.get(key) if key else None
            if hit and now - hit[0] < self.cfg["cache_minutes"] * 60:
                t.status, t.message, t.cached = "done", hit[1], True
                log_immediately = True
            elif self.cfg["mode"] == "offline":
                t.status, t.message = "done", offline_answer(clean)
                log_immediately = True
            else:
                t.status = "working"
                if student_id is not None:
                    self.active_students.add(student_id)
                self.active_tickets[t.id] = t
                self.executor.submit(self._process_ticket, t)
        if log_immediately:
            self._log(t, 0)
        return t

    def ticket(self, tid: int, student_id) -> dict:
        with self.lock:
            t = self.tickets.get(tid)
            if not t or t.student_id != student_id:
                raise AIError("Вопрос не найден. Задай его ещё раз.")
            t.polled = time.time()
            if t.status in ("queued", "working"):
                return {"status": "working"}
            if t.status == "done":
                return {"status": "done", "message": t.message, "cached": t.cached}
            return {"status": "error", "error": t.error}

    # --- учитель ---
    def status(self) -> dict:
        self.trigger_bridge_check()
        with self.lock:
            avg = sum(self.durations) / len(self.durations) if self.durations else None
            active_list = [{"name": t.name, "pc": t.pc, "since": t.created} for t in self.active_tickets.values()]
            if len(active_list) > 1:
                names_str = ", ".join(x["name"] for x in active_list[:3])
                if len(active_list) > 3:
                    names_str += f" (+{len(active_list) - 3})"
                working = {"name": f"{names_str} ({len(active_list)} параллельно)", "since": active_list[0]["since"]}
            elif active_list:
                working = active_list[0]
            else:
                working = None

            return {"mode": self.cfg["mode"], "provider": self.cfg["provider"],
                    "ok": self.fails == 0, "last_error": self.last_error, "last_ok": self.last_ok,
                    "queue": [],
                    "active_count": len(active_list),
                    "working": working,
                    "avg_seconds": round(avg, 1) if avg else None,
                    "configured": self._configured_locked(),
                    "bridge": dict(self._bridge_info) if self._bridge_info else None}

    def student_status(self) -> dict:
        with self.lock:
            return {"mode": self.cfg["mode"], "ok": self.fails == 0, "queue": 0, "active": len(self.active_tickets)}

    def set_mode(self, mode: str) -> None:
        if mode not in ("live", "offline", "pause"):
            raise AIError("Неизвестный режим")
        self.save_config({"mode": mode})
        to_log: list[Ticket] = []
        if mode != "live":
            with self.lock:
                for t in list(self.active_tickets.values()):
                    if t.status not in ("queued", "working"):
                        continue
                    if mode == "offline":
                        t.status, t.message = "done", offline_answer(t.messages)
                    else:
                        t.status, t.error = "error", "учитель поставил нейросеть на паузу"
                    self.active_tickets.pop(t.id, None)
                    self.active_students.discard(t.student_id)
                    to_log.append(t)
        for t in to_log:
            self._log(t, 0)

    def test(self) -> dict:
        """Проверка связи из пульта: тестовый короткий запрос напрямую."""
        self.check_bridge(force_fetch=True)
        t = Ticket(0, None, "учитель", "", [{"role": "user", "content": "Ответь одним словом: работаешь?"}], 0.1, 256, None)
        start = time.time()
        try:
            msg = self._call(t)
            self._mark_ok(time.time() - start)
            return {"ok": True, "answer": msg.get("content"), "seconds": round(time.time() - start, 1)}
        except AIError as e:
            self._mark_fail(str(e))
            return {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001
            self._mark_fail(str(e))
            return {"ok": False, "error": str(e)}

    def shutdown(self) -> None:
        """Останавливает фоновый поток проверки моста и пул потоков."""
        self._stop_event.set()
        self._bridge_event.set()
        if self._bridge_thread.is_alive():
            self._bridge_thread.join(timeout=2.0)
        self.executor.shutdown(wait=False, cancel_futures=True)

    # --- внутреннее ---
    def _configured_locked(self) -> bool:
        if self.cfg["provider"] == "gigachat":
            return bool(self.cfg.get("gigachat_key"))
        return bool(self.cfg.get("openai_base_url") and self.cfg.get("openai_models"))

    def _configured(self) -> bool:
        with self.lock:
            return self._configured_locked()

    def _cache_key_locked(self, t: Ticket) -> str | None:
        if t.temperature > 0.3 or t.tools or self.cfg["cache_minutes"] <= 0:
            return None
        raw = json.dumps([t.messages, t.max_tokens, self.cfg["provider"]], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _call(self, t: Ticket) -> dict:
        with self.lock:
            cfg = dict(self.cfg)
        if cfg.get("provider") == "openai":
            self.trigger_bridge_check()
            with self.lock:
                cfg = dict(self.cfg)
        provider = self.providers.get(cfg["provider"])
        if not provider:
            raise AIError("неизвестный поставщик нейросети")
        return provider.chat(cfg, t.messages, t.temperature, t.max_tokens, t.tools)

    def _mark_ok(self, seconds: float) -> None:
        with self.lock:
            self.fails = 0
            self.last_error = ""
            self.last_ok = time.time()
            self.durations.append(seconds)

    def _mark_fail(self, err: str) -> None:
        with self.lock:
            self.fails += 1
            self.last_error = err

    def _log(self, t: Ticket, ms: int) -> None:
        if not self.log_fn or t.student_id is None:
            return
        with self.lock:
            if t.logged:
                return
            t.logged = True
        try:
            self.log_fn(t, ms)
        except Exception:  # noqa: BLE001 — лента не должна ломать ответы
            pass

    def _gc(self) -> None:
        """Вызывается под self.lock."""
        now = time.time()
        stale = now - TICKET_STALE
        for tid, t in list(self.active_tickets.items()):
            if t.polled < stale:
                t.status = "error"
                t.error = "ученик закрыл запрос"
                self.active_tickets.pop(tid, None)
                self.active_students.discard(t.student_id)
        old = now - 600
        for tid in [k for k, t in self.tickets.items() if t.status in ("done", "error") and t.polled < old]:
            del self.tickets[tid]
        cache_ttl = self.cfg["cache_minutes"] * 60
        for k in [k for k, (ts, _) in self.cache.items() if now - ts > cache_ttl]:
            del self.cache[k]
        for sid, ts in list(self.last_ask.items()):
            if now - ts > 3600:
                del self.last_ask[sid]

    def _process_ticket(self, t: Ticket) -> None:
        start = time.time()
        should_log = False
        try:
            try:
                msg = self._call(t)
            except AIError:
                with self.lock:
                    old_url = self.cfg.get("openai_base_url")
                    is_openai = self.cfg.get("provider") == "openai"
                if is_openai and self.check_bridge(force_fetch=True):
                    with self.lock:
                        new_url = self.cfg.get("openai_base_url")
                    if new_url != old_url:
                        msg = self._call(t)
                    else:
                        raise
                else:
                    raise
            dur = time.time() - start
            self._mark_ok(dur)
            with self.lock:
                if t.status in ("queued", "working"):
                    t.status, t.message = "done", msg
                    key = self._cache_key_locked(t)
                    if key:
                        self.cache[key] = (time.time(), msg)
                    should_log = True
            if should_log:
                self._log(t, int(dur * 1000))
        except AIError as e:
            self._mark_fail(str(e))
            with self.lock:
                if t.status in ("queued", "working"):
                    t.status, t.error = "error", "нейросеть сейчас недоступна, попробуй через минуту"
                    should_log = True
            if should_log:
                self._log(t, int((time.time() - start) * 1000))
        except Exception as e:  # noqa: BLE001
            self._mark_fail(f"ошибка шлюза: {e!r}")
            with self.lock:
                if t.status in ("queued", "working"):
                    t.status, t.error = "error", "нейросеть сейчас недоступна, попробуй через минуту"
        finally:
            with self.lock:
                self.active_students.discard(t.student_id)
                self.active_tickets.pop(t.id, None)


def flags_for(text: str) -> list[str]:
    """Пометки для учителя: в вопросе похоже на личные данные или просьбу написать код."""
    out = ["личные данные?"] if PERSONAL.search(text or "") else []
    if ASKS_CODE.search(text or ""):
        out.append("просит код?")
    return out


def basic_auth_key(client_id: str, secret: str) -> str:
    """Ключ авторизации GigaChat из Client ID и Client Secret (если в кабинете выдали их по отдельности)."""
    return base64.b64encode(f"{client_id}:{secret}".encode()).decode()
