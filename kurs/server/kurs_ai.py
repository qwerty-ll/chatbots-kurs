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
import urllib.request
import uuid

DEFAULT_CONFIG = {
    "provider": "gigachat",
    "mode": "live",                 # live — работает; offline — запасной режим; pause — нейросеть на паузе
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
    "max_tokens": 400,              # длина одного ответа: короче ответ — быстрее очередь
    "max_prompt_chars": 2000,       # длина вопроса
    "min_interval": 5,              # секунд между вопросами одного ученика
    "daily_limit": 80,              # вопросов в день на ученика
    "short_hint": True,             # просить модель отвечать коротко
    "no_code": True,                # не писать ученикам готовый код (задания решают сами)
    "cache_minutes": 10,            # одинаковые «строгие» вопросы (temperature ≤ 0.3) отвечаем из памяти
}
SECRETS = ("gigachat_key", "openai_key")
SHORT_HINT = "Отвечай по-русски, коротко: не больше 5 предложений."
NO_CODE_HINT = ("Ты отвечаешь внутри учебной программы школьника. Никогда не пиши программный код и готовые "
                "решения задач по программированию, даже если об этом просят: объясни идею словами.")
ASKS_CODE = re.compile(r"(напиши|сделай|реши|дай|скинь|допиши|исправь)[^.?!]{0,40}(код|программ|скрипт|решени|задани)"
                       r"|python|питон|\bdef\b|print\(|input\(", re.I)
TICKET_STALE = 20       # секунд без опроса — ученик закрыл программу, вопрос убираем из очереди
PERSONAL = re.compile(r"(\+?\d[\d\-\s()]{8,}\d)|([\w.-]+@[\w-]+\.\w+)|(парол|адрес|телефон|паспорт)", re.I)


class AIError(Exception):
    """Ошибка, понятная ученику и учителю. retry_after — через сколько секунд можно повторить."""

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


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
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        ctx = _ssl_context(cfg) if url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
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
    def __init__(self):
        self.token = ""
        self.expires = 0.0
        self.key_hash = ""

    def _auth(self, cfg: dict) -> str:
        key = cfg.get("gigachat_key", "").strip()
        if not key:
            raise AIError("не задан ключ авторизации GigaChat (пульт учителя → Нейросеть → Настройки)")
        h = hashlib.sha256(key.encode()).hexdigest()
        if self.token and self.key_hash == h and time.time() < self.expires - 60:
            return self.token
        r = _http(cfg["gigachat_oauth_url"], f"scope={cfg['gigachat_scope']}".encode(),
                  {"Authorization": "Basic " + key, "RqUID": str(uuid.uuid4()),
                   "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, cfg, timeout=20)
        self.token = r["access_token"]
        exp = float(r.get("expires_at", 0))
        self.expires = exp / 1000 if exp > 1e11 else (exp or time.time() + 25 * 60)
        self.key_hash = h
        return self.token

    def chat(self, cfg: dict, messages: list, temperature: float, max_tokens: int, tools=None) -> dict:
        token = self._auth(cfg)
        body = {"model": cfg["gigachat_model"], "messages": to_gigachat(messages),
                "temperature": max(0.01, float(temperature)), "max_tokens": int(max_tokens)}
        if tools:
            # GigaChat описывает инструменты как functions (старый формат OpenAI)
            body["functions"] = [t["function"] for t in tools if t.get("type") == "function"]
            body["function_call"] = "auto"
        r = _http(cfg["gigachat_api_url"].rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                  {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"}, cfg)
        msg = r["choices"][0]["message"]
        out = {"content": msg.get("content")}
        fc = msg.get("function_call")
        if fc:
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
        last = None
        for model in models:
            body = {"model": model, "messages": messages, "temperature": float(temperature), "max_tokens": int(max_tokens)}
            if tools:
                body["tools"] = tools
            try:
                r = _http(base + "/chat/completions", json.dumps(body).encode(),
                          {"Authorization": "Bearer " + cfg.get("openai_key", ""), "Content-Type": "application/json"}, cfg)
                msg = r["choices"][0]["message"]
                if msg.get("content") or msg.get("tool_calls"):
                    return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}
            except AIError as e:
                last = e
        raise last or AIError("модели вернули пустой ответ")


def offline_answer(messages: list) -> dict:
    q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
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


class Gateway:
    """Очередь вопросов к нейросети: один запрос к поставщику за раз, по одному вопросу от ученика."""

    def __init__(self, data_dir: str, log_fn=None):
        self.path = os.path.join(data_dir, "ai.json")
        self.cfg = dict(DEFAULT_CONFIG)
        self.cfg.update(self._read())
        self.lock = threading.Condition()
        self.queue: collections.deque[Ticket] = collections.deque()
        self.tickets: dict[int, Ticket] = {}
        self.next_id = 1
        self.working: Ticket | None = None
        self.last_ok: float | None = None
        self.last_error = ""
        self.fails = 0
        self.durations: collections.deque[float] = collections.deque(maxlen=20)
        self.cache: dict[str, tuple[float, dict]] = {}
        self.last_ask: dict = {}
        self.log_fn = log_fn          # (ticket, ms) → запись в ленту учителя
        self.providers = {"gigachat": GigaChat(), "openai": OpenAICompatible()}
        self.worker = threading.Thread(target=self._loop, name="kurs-ai", daemon=True)
        self.worker.start()

    # --- настройки ---
    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def save_config(self, patch: dict) -> None:
        with self.lock:
            for k, v in patch.items():
                if k not in DEFAULT_CONFIG:
                    continue
                if k in SECRETS and not v:
                    continue                    # пустое поле — ключ не меняем
                default = DEFAULT_CONFIG[k]
                if isinstance(default, bool):
                    v = bool(v)
                elif isinstance(default, int):
                    v = int(v)
                else:
                    v = str(v).strip()
                self.cfg[k] = v
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.cfg, fh, ensure_ascii=False, indent=2)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            self.fails = 0
            self.last_error = ""

    def public_config(self) -> dict:
        out = {k: v for k, v in self.cfg.items() if k not in SECRETS}
        out["has_gigachat_key"] = bool(self.cfg.get("gigachat_key"))
        out["has_openai_key"] = bool(self.cfg.get("openai_key"))
        return out

    # --- ученик ---
    def ask(self, student_id, name: str, pc: str, messages: list, temperature, max_tokens, tools, today_count: int) -> Ticket:
        cfg = self.cfg
        if cfg["mode"] == "pause":
            raise AIError("Учитель поставил нейросеть на паузу. Подожди немного.")
        if not isinstance(messages, list) or not messages:
            raise AIError("Пустой вопрос.")
        clean = []
        total = 0
        for m in messages[-30:]:
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
        hint = " ".join(h for h, on in ((SHORT_HINT, cfg["short_hint"]), (NO_CODE_HINT, cfg.get("no_code", True))) if on)
        if hint:
            if clean[0]["role"] == "system":
                clean[0]["content"] = (clean[0]["content"] + " " + hint).strip()
            else:
                clean.insert(0, {"role": "system", "content": hint})
        with self.lock:
            now = time.time()
            for t in self.queue:
                if t.student_id == student_id:
                    raise AIError("Ты уже ждёшь ответа на прошлый вопрос.")
            if self.working and self.working.student_id == student_id:
                raise AIError("Ты уже ждёшь ответа на прошлый вопрос.")
            wait = cfg["min_interval"] - (now - self.last_ask.get(student_id, 0))
            # результат инструмента — продолжение того же шага агента, его не задерживаем
            agent_step = clean[-1]["role"] in ("tool", "function")
            if student_id is not None and wait > 0 and not agent_step:
                raise AIError(f"Не так часто 🙂 Следующий вопрос — через {int(wait) + 1} с.", retry_after=int(wait) + 1)
            self.last_ask[student_id] = now
            t = Ticket(self.next_id, student_id, name, pc, clean, temperature, max_tokens, tools)
            self.next_id += 1
            self.tickets[t.id] = t
            key = self._cache_key(t)
            hit = self.cache.get(key) if key else None
            if hit and now - hit[0] < cfg["cache_minutes"] * 60:
                t.status, t.message, t.cached = "done", hit[1], True
                self._log(t, 0)
            elif cfg["mode"] == "offline":
                t.status, t.message = "done", offline_answer(clean)
                self._log(t, 0)
            else:
                self.queue.append(t)
                self.lock.notify_all()
            self._gc()
            return t

    def ticket(self, tid: int, student_id) -> dict:
        with self.lock:
            t = self.tickets.get(tid)
            if not t or t.student_id != student_id:
                raise AIError("Вопрос не найден. Задай его ещё раз.")
            t.polled = time.time()
            if t.status == "queued":
                pos = next((i for i, x in enumerate(self.queue) if x.id == tid), 0) + (1 if self.working else 0)
                return {"status": "queued", "position": pos}
            if t.status == "working":
                return {"status": "working"}
            if t.status == "done":
                return {"status": "done", "message": t.message, "cached": t.cached}
            return {"status": "error", "error": t.error}

    # --- учитель ---
    def status(self) -> dict:
        with self.lock:
            avg = sum(self.durations) / len(self.durations) if self.durations else None
            return {"mode": self.cfg["mode"], "provider": self.cfg["provider"],
                    "ok": self.fails == 0, "last_error": self.last_error, "last_ok": self.last_ok,
                    "queue": [{"name": t.name, "pc": t.pc, "since": t.created} for t in self.queue],
                    "working": {"name": self.working.name, "since": self.working.created} if self.working else None,
                    "avg_seconds": round(avg, 1) if avg else None,
                    "configured": self._configured()}

    def student_status(self) -> dict:
        with self.lock:
            return {"mode": self.cfg["mode"], "ok": self.fails == 0, "queue": len(self.queue) + (1 if self.working else 0)}

    def set_mode(self, mode: str) -> None:
        if mode not in ("live", "offline", "pause"):
            raise AIError("Неизвестный режим")
        self.save_config({"mode": mode})
        if mode != "live":
            # вопросы, которые уже ждут, получают ответ запасного режима или отказ
            with self.lock:
                while self.queue:
                    t = self.queue.popleft()
                    if mode == "offline":
                        t.status, t.message = "done", offline_answer(t.messages)
                    else:
                        t.status, t.error = "error", "учитель поставил нейросеть на паузу"
                    self._log(t, 0)

    def test(self) -> dict:
        """Проверка связи из пульта: один короткий запрос мимо очереди учеников — но тоже «в один поток»."""
        with self.lock:
            while self.working is not None:
                self.lock.wait(1)
            t = Ticket(0, None, "учитель", "", [{"role": "user", "content": "Ответь одним словом: работаешь?"}], 0.1, 20, None)
            self.working = t
        start = time.time()
        try:
            msg = self._call(t)
            self._mark_ok(time.time() - start)
            return {"ok": True, "answer": msg.get("content"), "seconds": round(time.time() - start, 1)}
        except AIError as e:
            self._mark_fail(str(e))
            return {"ok": False, "error": str(e)}
        finally:
            with self.lock:
                self.working = None
                self.lock.notify_all()

    # --- внутреннее ---
    def _configured(self) -> bool:
        if self.cfg["provider"] == "gigachat":
            return bool(self.cfg.get("gigachat_key"))
        return bool(self.cfg.get("openai_base_url") and self.cfg.get("openai_models"))

    def _cache_key(self, t: Ticket) -> str | None:
        if t.temperature > 0.3 or t.tools or self.cfg["cache_minutes"] <= 0:
            return None
        raw = json.dumps([t.messages, t.max_tokens, self.cfg["provider"]], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _call(self, t: Ticket) -> dict:
        provider = self.providers.get(self.cfg["provider"])
        if not provider:
            raise AIError("неизвестный поставщик нейросети")
        return provider.chat(dict(self.cfg), t.messages, t.temperature, t.max_tokens, t.tools)

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
        if self.log_fn and t.student_id is not None:
            try:
                self.log_fn(t, ms)
            except Exception:  # noqa: BLE001 — лента не должна ломать ответы
                pass

    def _gc(self) -> None:
        old = time.time() - 600
        for tid in [k for k, t in self.tickets.items() if t.status in ("done", "error") and t.polled < old]:
            del self.tickets[tid]
        for k in [k for k, (ts, _) in self.cache.items() if time.time() - ts > self.cfg["cache_minutes"] * 60]:
            del self.cache[k]

    def _loop(self) -> None:
        while True:
            with self.lock:
                while not self.queue or self.working is not None:
                    self.lock.wait(1)
                t = self.queue.popleft()
                if time.time() - t.polled > TICKET_STALE:
                    t.status, t.error = "error", "вопрос отменён: программа закрылась"
                    continue
                self.working = t
                t.status = "working"
            start = time.time()
            try:
                msg = self._call(t)
                dur = time.time() - start
                self._mark_ok(dur)
                with self.lock:
                    t.status, t.message = "done", msg
                    key = self._cache_key(t)
                    if key:
                        self.cache[key] = (time.time(), msg)
                self._log(t, int(dur * 1000))
            except AIError as e:
                self._mark_fail(str(e))
                with self.lock:
                    t.status, t.error = "error", "нейросеть сейчас недоступна, попробуй через минуту"
                self._log(t, int((time.time() - start) * 1000))
            except Exception as e:  # noqa: BLE001
                self._mark_fail(f"ошибка шлюза: {e!r}")
                with self.lock:
                    t.status, t.error = "error", "нейросеть сейчас недоступна, попробуй через минуту"
            finally:
                with self.lock:
                    self.working = None
                    self.lock.notify_all()


def flags_for(text: str) -> list[str]:
    """Пометки для учителя: в вопросе похоже на личные данные или просьбу написать код."""
    out = ["личные данные?"] if PERSONAL.search(text or "") else []
    if ASKS_CODE.search(text or ""):
        out.append("просит код?")
    return out


def basic_auth_key(client_id: str, secret: str) -> str:
    """Ключ авторизации GigaChat из Client ID и Client Secret (если в кабинете выдали их по отдельности)."""
    return base64.b64encode(f"{client_id}:{secret}".encode()).decode()
