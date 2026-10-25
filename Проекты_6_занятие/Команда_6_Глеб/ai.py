# Модуль ai.py — «пульт управления нейросетью».
#
# На занятии 3 разбираем этот файл по строкам. Дальше во всех ботах
# подключаем его одной строкой:   from ai import ask
#
# Устанавливать ничего не нужно: работает на обычном Python, без библиотек.
# Настройки лежат в файле .env рядом с этим файлом.
#
#   В классе (файл .env создаёт панель курса):
#       KURS_SERVER=http://192.168.1.10:8000   сервер курса на компьютере учителя
#       API_KEY=...                            твой ключ класса — никому не показывай
#
#   Дома, напрямую к сервису с нейросетью (OpenAI-совместимый API):
#       BASE_URL=https://адрес-сервиса/v1
#       API_KEY=твой-ключ
#       MODELS=модель1,модель2

import json
import os
import sys
import time
import urllib.error
import urllib.request
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """Читает файл .env: каждая строка вида НАЗВАНИЕ=значение.

    Ищет .env рядом с ai.py, в текущей папке и в папках выше: так ничего не нужно настраивать руками.
    """
    folders = []
    for start in (HERE, os.getcwd()):
        folder = start
        for _ in range(4):
            if folder not in folders:
                folders.append(folder)
            folder = os.path.dirname(folder)
    for folder in folders:
        path = os.path.join(folder, ".env")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    name, value = line.split("=", 1)
                    os.environ.setdefault(name.strip(), value.strip().strip('"'))


load_env()                                      # читаем настройки из файла .env

API_KEY = os.getenv("API_KEY", "")
KURS_SERVER = os.getenv("KURS_SERVER", "").rstrip("/")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
MODELS = [m.strip() for m in os.getenv("MODELS", "").split(",") if m.strip()]

if not API_KEY or API_KEY.startswith("sk-впиши") or not (KURS_SERVER or (BASE_URL and MODELS)):
    raise SystemExit("Нет настроек! Нужен файл .env рядом с ai.py (в классе его создаёт панель курса).")


def send(url, data=None, timeout=60):
    """Отправляет запрос по адресу url и возвращает ответ (словарь).

    Заголовок Authorization: Bearer <ключ> — это наш «пропуск» к сервису.
    """
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + API_KEY)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def error_text(error):
    """Понятное сообщение об ошибке запроса."""
    if isinstance(error, urllib.error.HTTPError):
        detail = getattr(error, "detail", None)
        if detail is None:
            try:
                detail = json.loads(error.read().decode("utf-8")).get("error", "")
                if isinstance(detail, dict):
                    detail = detail.get("message", "")
            except (ValueError, AttributeError):
                detail = ""
        if error.code == 401:
            return detail or "неверный ключ (проверь API_KEY в .env)"
        if error.code == 429:
            return detail or "слишком много запросов, подожди немного"
        return detail or f"ошибка сервиса {error.code}"
    if isinstance(error, urllib.error.URLError):
        return "нет связи (проверь интернет или сервер курса)"
    return str(error)


def as_message(data):
    """Превращает ответ-словарь в объект: message.content, message.tool_calls."""
    calls = []
    for c in data.get("tool_calls") or []:
        function = SimpleNamespace(name=c["function"]["name"], arguments=c["function"].get("arguments", "{}"))
        calls.append(SimpleNamespace(id=c.get("id", ""), type="function", function=function))
    return SimpleNamespace(role="assistant", content=data.get("content"), tool_calls=calls or None)


def chat(messages, tools=None, temperature=0.7, max_tokens=1500):
    """Отправляет переписку модели и возвращает её сообщение (или None, если не вышло)."""
    if KURS_SERVER:
        return chat_in_class(messages, tools, temperature, max_tokens)
    return chat_direct(messages, tools, temperature, max_tokens)


def chat_in_class(messages, tools, temperature, max_tokens):
    """В классе: вопрос встаёт в очередь на сервере курса, ждём своей очереди."""
    data = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        data["tools"] = tools
    try:
        ticket = ask_server(data)
        shown = None
        while True:
            state = send(KURS_SERVER + "/api/ai/ticket?id=" + str(ticket["ticket"]), timeout=15)
            if state["status"] == "done":
                return as_message(state["message"])
            if state["status"] == "error":
                print(f"  (нейросеть не ответила: {state['error']})")
                return None
            # пока ждём — показываем, что происходит
            if state["status"] == "queued" and state.get("position", 0) > 0:
                text = f"⏳ Ты в очереди к нейросети, перед тобой: {state['position']}"
            else:
                text = "⏳ Нейросеть думает…"
            if text != shown and (shown is None or "думает" in text):
                print(text, flush=True)
                shown = text
            time.sleep(1)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
        print(f"  (нейросеть не ответила: {error_text(error)})")
        return None


def ask_server(data):
    """Ставит вопрос в очередь. Если сервер просит подождать пару секунд — ждём и пробуем снова."""
    for _ in range(3):
        try:
            return send(KURS_SERVER + "/api/ai/ask", data, timeout=15)
        except urllib.error.HTTPError as error:
            body = {}
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (ValueError, AttributeError):
                pass
            if not isinstance(body, dict):
                body = {}
            error.detail = body.get("error", "")          # тело ответа уже прочитано — сохраняем текст ошибки
            wait = body.get("retry_after")
            if error.code != 429 or not wait or wait > 30:
                raise
            print(f"⏳ Подожди {wait} с…", flush=True)
            time.sleep(wait)
    return send(KURS_SERVER + "/api/ai/ask", data, timeout=15)


def chat_direct(messages, tools, temperature, max_tokens):
    """Дома: напрямую к сервису. Пробуем модели из списка MODELS по очереди."""
    for model in MODELS:
        data = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            data["tools"] = tools                  # инструменты для агента (занятие 7)
        try:
            response = send(BASE_URL + "/chat/completions", data)
            message = response["choices"][0]["message"]
            if not message.get("content") and not message.get("tool_calls"):
                print(f"  (модель {model} вернула пустой ответ, пробую другую)")
                continue
            return as_message(message)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            print(f"  (модель {model} не ответила: {error_text(error)}, пробую другую)")
    return None


def chat_text(messages, temperature=0.7, max_tokens=1500, **options):
    """То же, что chat(), но возвращает только текст ответа."""
    message = chat(messages, temperature=temperature, max_tokens=max_tokens)
    if message is None:
        return "Нейросеть сейчас недоступна. Попробуй через минуту."
    return message.content or "(пустой ответ)"


def ask(question, system=None, temperature=0.7, max_tokens=1500, **options):
    """Самое простое: задать один вопрос и получить текст.

    system — необязательная «роль» бота (например: «Ты весёлый пират»).
    temperature — творчество (0.0 — строго, 1.0 — фантазия).
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})
    return chat_text(messages, temperature=temperature, max_tokens=max_tokens, **options)


if __name__ == "__main__":
    # Проверка: python ai.py
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(ask("Скажи одним предложением: ты работаешь?"))
