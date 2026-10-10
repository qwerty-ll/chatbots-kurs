#!/usr/bin/env python3
"""Запуск курса «Чат-боты на Python» на компьютере ученика.

  python3 kurs_start.py --server http://192.168.1.10:8000      первый запуск: запомнить сервер и открыть курс
  python3 kurs_start.py                                        следующие запуски
  python3 kurs_start.py --shortcut                             положить ярлык «Курс» на рабочий стол
  python3 kurs_start.py --uninstall                            убрать всё, что поставил курс

Что делает:
  1. Берёт с сервера свежую панель курса и ставит её в ОТДЕЛЬНЫЙ профиль VS Code (~/.kurs).
     Обычный VS Code пользователя, его настройки и расширения не меняются.
  2. Готовит папку ~/Курс и открывает её в VS Code с панелью курса.

Нужна только стандартная библиотека Python 3.8+ и установленный VS Code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.request

HOME = os.path.expanduser("~")
KURS_HOME = os.path.join(HOME, ".kurs")
PROFILE = os.path.join(KURS_HOME, "vscode-profile")
EXTDIR = os.path.join(KURS_HOME, "vscode-extensions")
WORKSPACE = os.path.join(HOME, "Курс")
STATE = os.path.join(KURS_HOME, "state.json")
# Адрес сервера подставляет сам сервер, когда отдаёт этот файл по короткому адресу /k
DEFAULT_SERVER = ""

# Настройки отдельного профиля VS Code: крупно, без лишнего, без «умных» подсказок ИИ
SETTINGS = {
    "editor.fontSize": 18,
    "terminal.integrated.fontSize": 16,
    "editor.tabSize": 4,
    "editor.insertSpaces": True,
    "editor.detectIndentation": False,
    "editor.autoClosingBrackets": "always",
    "editor.autoClosingQuotes": "always",
    "editor.minimap.enabled": False,
    "editor.wordWrap": "on",
    "editor.renderWhitespace": "boundary",
    "editor.inlineSuggest.enabled": False,
    "files.autoSave": "afterDelay",
    "files.autoSaveDelay": 1000,
    "files.encoding": "utf8",
    "workbench.startupEditor": "none",
    "workbench.tips.enabled": False,
    "workbench.enableExperiments": False,
    "security.workspace.trust.enabled": False,
    "extensions.ignoreRecommendations": True,
    "extensions.autoUpdate": False,
    "update.mode": "none",
    "telemetry.telemetryLevel": "off",
    "chat.disableAIFeatures": True,
    "chat.commandCenter.enabled": False,
    "git.enabled": False,
    "window.restoreWindows": "none",
    "workbench.secondarySideBar.defaultVisibility": "hidden",
    # «простой вид»: слева редактор, справа панель курса, без лишних кнопок
    "workbench.activityBar.location": "hidden",
    "workbench.layoutControl.enabled": False,
    "window.commandCenter": False,
    "breadcrumbs.enabled": False,
    "editor.stickyScroll.enabled": False,
    "terminal.integrated.enablePersistentSessions": False,
    "workbench.colorTheme": "Default Light Modern",
    "workbench.welcomePage.walkthroughs.openOnInstall": False,
    "diffEditor.renderSideBySide": False,
    "terminal.integrated.hideOnStartup": "always",
}


def say(msg: str) -> None:
    print(msg, flush=True)


def read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def find_code() -> str | None:
    """Ищет команду запуска VS Code."""
    for name in ("code", "code-oss", "codium"):
        p = shutil.which(name)
        if p:
            return p
    cands = []
    if sys.platform == "darwin":
        cands += ["/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
                  os.path.join(HOME, "Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")]
    elif os.name == "nt":
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            cands.append(os.path.join(base, "Programs", "Microsoft VS Code", "bin", "code.cmd"))
            cands.append(os.path.join(base, "Microsoft VS Code", "bin", "code.cmd"))
    else:
        cands += ["/usr/bin/code", "/usr/share/code/bin/code", "/snap/bin/code", "/usr/local/bin/code",
                  "/var/lib/flatpak/exports/bin/com.visualstudio.code"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def fetch(url: str, timeout: int = 15) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def code_cmd(code: str, *args: str) -> list[str]:
    base = [code, "--user-data-dir", PROFILE, "--extensions-dir", EXTDIR]
    if os.name == "nt" and code.lower().endswith(".cmd"):
        return ["cmd", "/c"] + base + list(args)
    return base + list(args)


def reset_ui_state() -> None:
    """Каждый запуск — чистое окно: без вкладок, терминалов и панелей, оставшихся от прошлого ученика."""
    for rel in (("User", "workspaceStorage"), ("Backups",), ("User", "History"), ("Workspaces",)):
        shutil.rmtree(os.path.join(PROFILE, *rel), ignore_errors=True)


def install_panel(server: str, code: str) -> None:
    man = json.loads(fetch(server + "/client/manifest.json"))
    state = read_json(STATE, {})
    if state.get("sha256") == man["sha256"] and os.path.isdir(EXTDIR) and os.listdir(EXTDIR):
        say(f"Панель курса {man['version']} уже установлена.")
        return
    say(f"Скачиваю панель курса {man['version']}…")
    data = fetch(server + "/client/" + man["vsix"], timeout=60)
    if hashlib.sha256(data).hexdigest() != man["sha256"]:
        raise SystemExit("Файл панели скачался с ошибкой. Попробуйте ещё раз.")
    vsix = os.path.join(KURS_HOME, "kurs-panel.vsix")
    with open(vsix, "wb") as fh:
        fh.write(data)
    r = subprocess.run(code_cmd(code, "--install-extension", vsix, "--force"), capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("Не удалось поставить панель в VS Code:\n" + (r.stderr or r.stdout)[-800:])
    state.update(sha256=man["sha256"], version=man["version"])
    write_json(STATE, state)
    say("Панель курса установлена.")


def prepare(server: str, pc: str | None) -> None:
    settings_file = os.path.join(PROFILE, "User", "settings.json")
    cur = read_json(settings_file, {})
    cur.update(SETTINGS)
    write_json(settings_file, cur)
    cfg_file = os.path.join(WORKSPACE, ".kurs", "config.json")
    cfg = read_json(cfg_file, {})
    cfg.update(server=server, python=sys.executable)
    if pc:
        cfg["pc"] = pc
    write_json(cfg_file, cfg)
    reset_ui_state()
    os.makedirs(os.path.join(WORKSPACE, "Мои_работы"), exist_ok=True)
    readme = os.path.join(WORKSPACE, "ПРОЧИТАЙ.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("Это папка курса «Чат-боты на Python».\n"
                     "Задания открываются в панели справа. Твои файлы — в папке Мои_работы.\n"
                     "В конце занятия файлы сохраняются у учителя и стираются с этого компьютера.\n")


def make_shortcut(server: str) -> None:
    me = os.path.join(KURS_HOME, "kurs_start.py")
    try:
        data = fetch(server + "/client/kurs_start.py")
        with open(me, "wb") as fh:
            fh.write(data)
    except OSError:
        if "__file__" in globals():
            shutil.copy(os.path.abspath(__file__), me)
    desktop = desktop_dir()
    os.makedirs(desktop, exist_ok=True)
    if os.name == "nt":
        path = os.path.join(desktop, "Курс.bat")
        with open(path, "w", encoding="cp866", errors="replace") as fh:
            fh.write(f'@echo off\r\n"{sys.executable}" "{me}"\r\n')
    elif sys.platform == "darwin":
        path = os.path.join(desktop, "Курс.command")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f'#!/bin/sh\n"{sys.executable}" "{me}"\n')
        os.chmod(path, 0o755)
    else:
        path = os.path.join(desktop, "kurs.desktop")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[Desktop Entry]\nType=Application\nName=Курс: чат-боты\n"
                     f'Exec="{sys.executable}" "{me}"\nIcon=accessories-text-editor\nTerminal=false\n')
        os.chmod(path, 0o755)
        # GNOME запускает ярлык с рабочего стола, только если он помечен как доверенный
        subprocess.run(["gio", "set", path, "metadata::trusted", "true"], capture_output=True, check=False)
    say(f"Ярлык создан: {path}")


def desktop_dir() -> str:
    """Папка рабочего стола: на русском Linux она может называться «Рабочий стол»."""
    if os.name != "nt" and sys.platform != "darwin" and shutil.which("xdg-user-dir"):
        r = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=False)
        path = r.stdout.strip()
        if r.returncode == 0 and path and path != HOME:
            return path
    for name in ("Desktop", "Рабочий стол"):
        if os.path.isdir(os.path.join(HOME, name)):
            return os.path.join(HOME, name)
    return os.path.join(HOME, "Desktop")


def uninstall() -> None:
    ans = input(f"Удалить {KURS_HOME} и {WORKSPACE}? Работы учеников на этом компьютере пропадут. (да/нет) ")
    if ans.strip().lower() != "да":
        say("Отменено.")
        return
    shutil.rmtree(KURS_HOME, ignore_errors=True)
    shutil.rmtree(WORKSPACE, ignore_errors=True)
    say("Готово: курс убран с компьютера.")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Запуск курса на компьютере ученика")
    ap.add_argument("--server", help="адрес сервера курса, например http://192.168.1.10:8000")
    ap.add_argument("--pc", help="имя компьютера в списке учителя (по умолчанию — сетевое имя)")
    ap.add_argument("--shortcut", action="store_true", help="создать ярлык на рабочем столе")
    ap.add_argument("--uninstall", action="store_true", help="убрать курс с компьютера")
    ap.add_argument("--no-open", action="store_true", help="только подготовить, VS Code не открывать")
    a = ap.parse_args(argv)
    if a.uninstall:
        uninstall()
        return 0
    os.makedirs(KURS_HOME, exist_ok=True)
    state = read_json(STATE, {})
    server = (a.server or os.environ.get("KURS_SERVER") or DEFAULT_SERVER or state.get("server") or "").strip().rstrip("/")
    if not server:
        server = input("Адрес сервера курса (скажет учитель), например 192.168.1.10:8000: ").strip().rstrip("/")
    if server and not server.startswith(("http://", "https://")):
        server = "http://" + server
    state["server"] = server
    write_json(STATE, state)
    code = find_code()
    if not code:
        say("Не найден VS Code. Позовите учителя: на компьютере нужен установленный Visual Studio Code.")
        return 1
    say(f"Компьютер: {a.pc or socket.gethostname().split('.')[0]} · {platform.system()} · Python {platform.python_version()}")
    try:
        install_panel(server, code)
    except OSError as e:
        say(f"Нет связи с сервером курса ({server}): {e}. Проверьте адрес и что учитель запустил сервер.")
        if not (os.path.isdir(EXTDIR) and os.listdir(EXTDIR)):
            return 1
        say("Открываю курс с уже установленной панелью.")
    prepare(server, a.pc)
    if a.shortcut:
        make_shortcut(server)
    if not a.no_open:
        kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000008}
        extra = []
        if sys.platform.startswith("linux"):
            # без этого VS Code на Linux просит разблокировать «связку ключей» — ученику это непонятно
            extra = ["--password-store=basic"]
        subprocess.Popen(code_cmd(code, *extra, "--new-window", WORKSPACE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        say("VS Code открывается…")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
