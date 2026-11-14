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
DEFAULT_MODELS = "gemini-3.8-flash-low,gemini-3.5-flash-lite,gemini-3.8-flash"
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


def _drain_pipe(proc: subprocess.Popen) -> None:
    """Фоновый сброс stdout/stderr, чтобы 64КБ буфер пайпа ОС не переполнялся и не вешал туннель."""
    try:
        while proc.poll() is None:
            line = (proc.stdout.readline() if proc.stdout else "") or (proc.stderr.readline() if proc.stderr else "")
            if not line:
                break
    except Exception:
        pass


def _start_drain_thread(proc: subprocess.Popen) -> None:
    import threading
    threading.Thread(target=_drain_pipe, args=(proc,), daemon=True).start()


def _stop_proc(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def start_tunnel() -> tuple[subprocess.Popen, str]:
    """Поднимает интернет-туннель: сначала cloudflared (стабильный), затем Pinggy SSH как резерв."""
    # 1. Предпочтительно cloudflared (не обрывается каждые 60 минут и не страдает от read timeout как Pinggy)
    cpath = shutil.which("cloudflared") or "/opt/homebrew/bin/cloudflared"
    if os.path.isfile(cpath):
        try:
            log("TUNNEL", f"Запускаю Cloudflare туннель для http://127.0.0.1:{PORT}…", BLUE)
            cmd = [cpath, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
            start = time.time()
            while time.time() - start < 20:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line and proc.poll() is not None:
                    break
                m = pattern.search(line)
                if m:
                    _start_drain_thread(proc)
                    return proc, m.group(0)
            _stop_proc(proc)
        except Exception as e:
            log("WARN", f"Cloudflare туннель не запустился: {e}", YELLOW)

    # 2. Резервный вариант через нативный SSH Pinggy
    ssh = shutil.which("ssh")
    if ssh:
        try:
            log("TUNNEL", f"Пробую резервный Pinggy туннель для http://127.0.0.1:{PORT}…", BLUE)
            cmd = [ssh, "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=20",
                   "-o", "ServerAliveCountMax=3", "-p", "443", f"-R0:localhost:{PORT}", "a.pinggy.io"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            pattern = re.compile(r"https://[a-zA-Z0-9.-]+\.(?:pinggy-free\.link|pinggy\.net)")
            start = time.time()
            while time.time() - start < 15:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line and proc.poll() is not None:
                    break
                m = pattern.search(line)
                if m:
                    _start_drain_thread(proc)
                    return proc, m.group(0)
            _stop_proc(proc)
        except Exception as e:
            log("WARN", f"Pinggy туннель не запустился: {e}", YELLOW)

    raise RuntimeError("Не удалось поднять ни cloudflared, ни Pinggy туннель")


def is_tunnel_healthy(base_url: str, key: str) -> bool:
    req = urllib.request.Request(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "kurs-bridge-health"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def test_ai(url: str, key: str) -> bool:
    model = DEFAULT_MODELS.split(",")[0].strip()
    req_data = {
        "model": model,
        "messages": [{"role": "user", "content": "Ответь одним словом: работаешь?"}],
        "max_tokens": 256,
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
    for attempt in range(1, 7):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                res = json.loads(r.read().decode("utf-8"))
                content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                log("AI", f"Ответ от {model} получен: «{content.strip()}»", GREEN)
                return True
        except Exception as e:
            if attempt < 6:
                time.sleep(2.0)
            else:
                log("WARN", f"Тест запроса через туннель: {e}", YELLOW)
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
        subprocess.run(["git", "-C", HERE, "pull", "--rebase", "--autostash", "origin", "main"],
                       capture_output=True, timeout=25, check=False)
        subprocess.run(["git", "-C", HERE, "add", "kurs/server/ai_bridge.json"], timeout=10, check=True)
        status = subprocess.run(["git", "-C", HERE, "diff", "--cached", "--quiet"], timeout=10, check=False)
        if status.returncode != 0:
            commit_msg = f"Auto-update AI bridge: {tunnel_url}"
            subprocess.run(["git", "-C", HERE, "commit", "-m", commit_msg], timeout=15, check=True)
            push_res = subprocess.run(["git", "-C", HERE, "push", "origin", "main"],
                                      capture_output=True, text=True, timeout=25, check=False)
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

    proc, tunnel_url = start_tunnel()
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
    print(f"   • Провайдер:        {YELLOW}Gemini 3.8 Flash Low (пул Antigravity Tools){RESET}")
    print(f"   • Автоподключение:  {GREEN}На учительском ПК адрес подхватится сам!{RESET}")
    print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"\n{YELLOW}Держите это окно открытым во время занятия. Для остановки нажмите Ctrl+C.{RESET}\n")

    def handle_sigint(sig, frame):
        print(f"\n{BLUE}Останавливаю туннель…{RESET}")
        save_bridge_config(tunnel_url, key, enabled=False)
        _stop_proc(proc)
        log("OK", "Мост остановлен. До встречи!", GREEN)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    last_health = time.time()
    bad_health = 0
    while True:
        need_reconnect = proc.poll() is not None
        if not need_reconnect and time.time() - last_health >= 45:
            last_health = time.time()
            if is_tunnel_healthy(f"{tunnel_url}/v1", key):
                bad_health = 0
            else:
                bad_health += 1
                if bad_health >= 2:
                    need_reconnect = True

        if need_reconnect:
            log("WARN", "Туннель закрылся или перестал отвечать. Переподключаю…", YELLOW)
            _stop_proc(proc)
            bad_health = 0
            time.sleep(2)
            try:
                proc, tunnel_url = start_tunnel()
                log("OK", f"Туннель переоткрыт: {BOLD}{tunnel_url}{RESET}", GREEN)
                test_ai(f"{tunnel_url}/v1", key)
                save_bridge_config(tunnel_url, key, enabled=True)
                sync_git(tunnel_url)
                last_health = time.time()
                log("OK", f"Мост обновлён и доступен: {tunnel_url}/v1", GREEN)
            except Exception as e:
                log("WARN", f"Ошибка переподключения: {e}. Повтор через 5 секунд…", YELLOW)
                time.sleep(5)
                continue
        time.sleep(2)


if __name__ == "__main__":
    main()
