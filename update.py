#!/usr/bin/env python3
"""Обновить курс на учительском ПК одной командой:  python3 update.py

1. Сохраняет копию данных сервера (группы, результаты, работы учеников, настройки нейросети)
   в ~/.kurs-server-backups/ДАТА — на случай, если что-то пойдёт не так.
2. Скачивает обновление (git pull). Не получилось — старый сервер продолжает работать как был.
3. Останавливает старый сервер (свой процесс kurs_server.py).
4. Просит панели учеников перезапустить VS Code и обновиться (как кнопка на пульте).
5. Запускает новый сервер в этом же окне (остановить — Ctrl+C).

Параметры: --port 8080, --data ПАПКА — если сервер запускали не с настройками по умолчанию
(обычно не нужны: их видно у запущенного сервера). --no-pull — только перезапустить.
--keep-clients — не перезапускать VS Code у учеников.
"""
import argparse
import contextlib
import getpass
import json
import os
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "kurs", "server", "kurs_server.py")
BACKUPS = os.path.expanduser("~/.kurs-server-backups")
KEEP_BACKUPS = 10


def say(msg: str) -> None:
    print(f"[обновление] {msg}", flush=True)


def _split_cmdline(cmdline: str) -> list[str]:
    try:
        return shlex.split(cmdline, posix=(os.name != "nt"))
    except ValueError:
        return cmdline.split()


def _is_kurs_server_cmd(cmdline: str) -> bool:
    """Проверяет, что процесс — именно Python с kurs_server.py (а не редактор или update.py)."""
    words = _split_cmdline(cmdline)
    if not words:
        return False
    exe = os.path.basename(words[0]).lower().removesuffix(".exe")
    is_python = exe == "py" or exe.startswith("python")
    if not is_python:
        return False
    has_server = any(os.path.basename(w.strip("\"'")) == "kurs_server.py" for w in words[1:])
    has_update = any(os.path.basename(w.strip("\"'")) == "update.py" for w in words[1:])
    return has_server and not has_update


def running_servers() -> list:
    """Запущенные серверы курса: [(pid, пользователь, аргументы)]."""
    if os.name == "nt":
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*kurs_server.py*' } | "
            "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
        )
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            )
            raw = r.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            rows = data if isinstance(data, list) else [data]
            me = getpass.getuser()
            found = []
            for row in rows:
                cmd = str(row.get("CommandLine") or "")
                pid = row.get("ProcessId")
                if pid and _is_kurs_server_cmd(cmd):
                    found.append((int(pid), me, cmd))
            return found
        except (OSError, ValueError, subprocess.SubprocessError):
            return []
    try:
        out = subprocess.run(["ps", "-eo", "pid=,user=,args="], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and _is_kurs_server_cmd(parts[2]):
            found.append((int(parts[0]), parts[1], parts[2]))
    return found


def option(args: str, name: str):
    words = _split_cmdline(args)
    for i, w in enumerate(words):
        if w == name and i + 1 < len(words):
            return words[i + 1].strip("\"'")
        if w.startswith(name + "="):
            return w.split("=", 1)[1].strip("\"'")
    return None


def port_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def backup(data: str) -> None:
    if not os.path.isdir(data):
        say("Данных сервера ещё нет — копировать нечего.")
        return
    dest = os.path.join(BACKUPS, time.strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(dest, exist_ok=True)
    if os.name != "nt":
        os.chmod(BACKUPS, 0o700)
    for name in os.listdir(data):
        src = os.path.join(data, name)
        if name.endswith(".sqlite3"):
            # база может быть открыта работающим сервером — копируем её штатным способом SQLite
            with contextlib.closing(sqlite3.connect(src, timeout=5.0)) as a, \
                    contextlib.closing(sqlite3.connect(os.path.join(dest, name), timeout=5.0)) as b:
                a.execute("PRAGMA busy_timeout=5000")
                b.execute("PRAGMA busy_timeout=5000")
                a.backup(b)
        elif os.path.isfile(src) and not name.endswith(("-wal", "-shm", "-journal")):
            shutil.copy2(src, dest)
    say(f"Копия данных сохранена: {dest}")
    old = sorted(os.listdir(BACKUPS))[:-KEEP_BACKUPS]
    for name in old:
        shutil.rmtree(os.path.join(BACKUPS, name), ignore_errors=True)


def pull() -> bool:
    if not os.path.isdir(os.path.join(HERE, ".git")):
        say("Папка скачана архивом, а не через git: скачайте новый ZIP и замените папку, потом запустите update.py снова.")
        return False
    r = subprocess.run(["git", "-C", HERE, "pull", "--ff-only"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        say("Не удалось скачать обновление (см. сообщение выше). Старый сервер не трогаю.")
        if "local changes" in r.stderr or "локальные изменения" in r.stderr:
            say("В папке есть изменённые файлы. Посмотреть: git status. Вернуть как было: git checkout -- .")
        return False
    return True


def _terminate_pid(pid: int, force: bool = False) -> bool:
    if os.name == "nt":
        if force:
            r = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
            return r.returncode == 0
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False


def stop(servers: list, port: int) -> bool:
    me = getpass.getuser()
    mine = [s for s in servers if s[1] == me]
    for pid, user, _ in servers:
        if user != me:
            say(f"Сервер пользователя «{user}» (процесс {pid}) остановить не могу — нужны его права.")
    if os.name == "nt":
        stages = [(False,), (True,)]
    else:
        stages = [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]
    for stage in stages:
        alive = []
        for pid, _, _ in mine:
            if os.name == "nt":
                if _terminate_pid(pid, force=stage[0]):
                    alive.append(pid)
            else:
                try:
                    os.kill(pid, stage)
                    alive.append(pid)
                except ProcessLookupError:
                    pass
        if not alive:
            break
        for _ in range(50):
            time.sleep(0.1)
            if not any(_alive(p) for p in alive):
                break
        mine = [s for s in mine if _alive(s[0])]
        if not mine:
            break
    if mine:
        say("Старый сервер не останавливается.")
        return False
    for _ in range(30):
        if port_free(port):
            return True
        time.sleep(0.2)
    say(f"Порт {port} всё ещё занят другой программой. Запустите на другом: python3 update.py --port {port + 1}")
    return False


def _alive(pid: int) -> bool:
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def restart_clients(data: str) -> None:
    db = os.path.join(data, "kurs.sqlite3")
    if not os.path.exists(db):
        return
    with contextlib.closing(sqlite3.connect(db, timeout=5.0)) as c:
        c.execute("PRAGMA busy_timeout=5000")
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='state'").fetchone()
        if not exists:
            return
        with c:
            row = c.execute("SELECT value FROM state WHERE key='restart_seq'").fetchone()
            seq = (json.loads(row[0]) if row else 0) + 1
            c.execute("INSERT INTO state(key,value) VALUES('restart_seq',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (json.dumps(seq),))
    say("Панели учеников перезапустят VS Code и обновятся сами (вход учеников сохранится).")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="Обновить курс на учительском ПК")
    ap.add_argument("--port", type=int)
    ap.add_argument("--data")
    ap.add_argument("--no-pull", action="store_true", help="не скачивать обновление, только перезапустить сервер")
    ap.add_argument("--keep-clients", action="store_true", help="не перезапускать VS Code у учеников")
    a = ap.parse_args(argv)

    servers = running_servers()
    seen = servers[0][2] if servers else ""
    port = a.port or int(option(seen, "--port") or 8000)
    data = os.path.expanduser(a.data or option(seen, "--data") or "~/.kurs-server")
    say(f"Сервер: {'запущен (процесс ' + str(servers[0][0]) + ')' if servers else 'не запущен'}, порт {port}, данные {data}")

    backup(data)
    if not a.no_pull and not pull():
        return 1
    if servers and not stop(servers, port):
        return 1
    if servers:
        say("Старый сервер остановлен.")
    if not a.keep_clients:
        restart_clients(data)
    say("Запускаю новый сервер. Пульт: войдите заново со своим паролем.")
    args = [sys.executable, SERVER, "--port", str(port), "--data", data]
    if os.name == "nt":
        return subprocess.call(args)
    os.execv(sys.executable, args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
