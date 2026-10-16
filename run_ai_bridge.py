#!/usr/bin/env python3
"""Пульт запуска ИИ-моста с ноутбука (Antigravity Tools -> Cloudflare Tunnel -> Git -> Сервер курса).

Что делает:
1. Проверяет, запущен ли Antigravity Tools (порт 8045). Если нет — запускает приложение.
2. Считывает ключ класса из ~/.antigravity_tools/class_key.txt.
3. Поднимает интернет-туннель через cloudflared на порт 8045.
4. Проверяет связь с нейросетью (Gemini 3 Flash).
5. Записывает адрес туннеля в kurs/server/ai_bridge.json.
6. Отправляет обновление в GitHub (git commit & git push origin main).
7. Сервер курса на учительском ПК подхватывает адрес автоматически (даже без перезапуска).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE_FILE = os.path.join(HERE, "kurs", "server", "ai_bridge.json")
CLASS_KEY_FILE = os.path.expanduser("~/.antigravity_tools/class_key.txt")
DEFAULT_KEY = "sk-class-b75732a69115bc0c7436a9b561db217509ec0de18069d43d"
DEFAULT_MODELS = "gemini-3.8-flash,gemini-3.x-flash"
PORT = 8045

# ANSI цвета
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(prefix: str, msg: str, color: str = "") -> None:
    print(f"{color}{BOLD}[{prefix}]{RESET} {msg}", flush=True)


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((host, port)) == 0


def ensure_antigravity_tools() -> None:
    if is_port_open(PORT):
        log("OK", "Antigravity Tools уже работает на порту 8045.", GREEN)
        return
    log("INFO", "Antigravity Tools не запущен. Запускаю приложение…", BLUE)
    subprocess.run(["open", "-a", "Antigravity Tools"], check=False)
    for _ in range(25):
        time.sleep(0.5)
        if is_port_open(PORT):
            log("OK", "Antigravity Tools успешно запущен и слушает порт 8045.", GREEN)
            return
    log("WARN", "Порт 8045 пока не отвечает, но продолжаю запуск туннеля…", YELLOW)


def get_class_key() -> str:
    if os.path.isfile(CLASS_KEY_FILE):
        try:
            with open(CLASS_KEY_FILE, encoding="utf-8") as fh:
                k = fh.read().strip()
                if k:
                    return k
        except OSError:
            pass
    return DEFAULT_KEY


def find_cloudflared() -> str:
    p = shutil.which("cloudflared")
    if p:
        return p
    for cand in ("/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"):
        if os.path.isfile(cand):
            return cand
    log("FAIL", "Утилита cloudflared не найдена в системе!", RED)
    print("Установите её через Homebrew командой: brew install cloudflared")
    sys.exit(1)


def test_ai(url: str, key: str) -> bool:
    req_data = {
        "model": "gemini-3.8-flash",
        "messages": [{"role": "user", "content": "Скажи одним словом: привет"}],
        "max_tokens": 10,
    }
    req = urllib.request.Request(
        f"{url}/chat/completions",
        data=json.dumps(req_data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "kurs-bridge-test",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
            log("AI", f"Ответ от Gemini 3 Flash получен: «{content.strip()}»", GREEN)
            return True
    except Exception as e:
        log("WARN", f"Тест запроса через туннель не удался: {e}", YELLOW)
        return False


def save_bridge_config(tunnel_url: str, key: str, enabled: bool = True) -> dict:
    os.makedirs(os.path.dirname(BRIDGE_FILE), exist_ok=True)
    conf = {
        "enabled": enabled,
        "provider": "openai",
        "openai_base_url": f"{tunnel_url}/v1",
        "openai_key": key,
        "openai_models": DEFAULT_MODELS,
        "updated_at": int(time.time()),
        "tunnel_url": tunnel_url,
        "hostname": socket.gethostname().split(".")[0],
    }
    with open(BRIDGE_FILE, "w", encoding="utf-8") as fh:
        json.dump(conf, fh, ensure_ascii=False, indent=2)
    return conf


def sync_git(tunnel_url: str) -> None:
    log("GIT", "Синхронизирую новый адрес туннеля с GitHub…", CYAN)
    try:
        subprocess.run(["git", "-C", HERE, "add", "kurs/server/ai_bridge.json",
                        "kurs/server/kurs_ai.py", "kurs/server/web/teacher.js"], check=True)
        # Проверяем, есть ли что коммитить
        status = subprocess.run(["git", "-C", HERE, "diff", "--cached", "--quiet"], check=False)
        if status.returncode != 0:
            commit_msg = f"Auto-update AI bridge: {tunnel_url}"
            subprocess.run(["git", "-C", HERE, "commit", "-m", commit_msg], check=True)
            push_res = subprocess.run(["git", "-C", HERE, "push", "origin", "main"], capture_output=True, text=True, check=False)
            if push_res.returncode == 0:
                log("GIT", "Адрес успешно отправлен в ветку main на GitHub!", GREEN)
            else:
                log("WARN", f"Не удалось выполнить push: {push_res.stderr.strip()}", YELLOW)
        else:
            log("GIT", "Конфигурация в Git уже актуальна.", GREEN)
    except Exception as e:
        log("WARN", f"Ошибка при синхронизации с Git: {e}", YELLOW)


def main() -> None:
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{GREEN}   🚀 ПУЛЬТ ИИ-МОСТА (Antigravity Tools ➔ Сервер курса){RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════════════════{RESET}\n")

    ensure_antigravity_tools()
    key = get_class_key()
    cpath = find_cloudflared()

    log("TUNNEL", f"Запускаю Cloudflare Tunnel для http://127.0.0.1:{PORT}…", BLUE)
    proc = subprocess.Popen(
        [cpath, "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Читаем stderr процесса, где cloudflared печатает назначенный адрес
    start_time = time.time()
    while time.time() - start_time < 20:
        line = proc.stderr.readline()
        if not line and proc.poll() is not None:
            break
        m = url_pattern.search(line)
        if m:
            tunnel_url = m.group(0)
            break

    if not tunnel_url:
        log("FAIL", "Не удалось получить адрес от Cloudflare за 20 секунд.", RED)
        proc.terminate()
        sys.exit(1)

    log("OK", f"Туннель открыт: {BOLD}{tunnel_url}{RESET}", GREEN)

    # Проверяем связь
    test_ai(f"{tunnel_url}/v1", key)

    # Сохраняем локальный конфиг
    save_bridge_config(tunnel_url, key, enabled=True)

    # Пушим в репозиторий GitHub
    sync_git(tunnel_url)

    print(f"\n{BOLD}{GREEN}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}✅ Мост ИИ успешно запущен и готов к работе с классом!{RESET}")
    print(f"   • Публичный адрес:  {CYAN}{tunnel_url}/v1{RESET}")
    print(f"   • Провайдер:        {YELLOW}Gemini 3.8 Flash (пул Antigravity Tools){RESET}")
    print(f"   • Автоподключение:  {GREEN}На учительском ПК адрес подхватится сам!{RESET}")
    print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"\n{YELLOW}Держите это окно открытым во время занятия. Для остановки нажмите Ctrl+C.{RESET}\n")

    def handle_sigint(sig, frame):
        print(f"\n{BLUE}Останавливаю туннель…{RESET}")
        save_bridge_config(tunnel_url, key, enabled=False)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        log("OK", "Мост остановлен. До встречи!", GREEN)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    while True:
        if proc.poll() is not None:
            log("FAIL", "Процесс туннеля неожиданно завершился.", RED)
            sys.exit(1)
        time.sleep(2)


if __name__ == "__main__":
    main()
