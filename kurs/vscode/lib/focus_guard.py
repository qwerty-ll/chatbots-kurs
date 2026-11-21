#!/usr/bin/env python3
"""Тихий сторож концентрации на компьютере ученика (без sudo и без уведомлений).

Поддерживает два независимых режима:
  --block-sites   Закрывает в браузерах и PWA ChatGPT, DeepSeek, Алису AI, ГигаЧат,
                  VK и другие отвлекающие ИИ-чаты/соцсети (вкладку или окно).
  --block-games   Жёсткий режим: закрывает игры (Minecraft, TLauncher, Steam, Roblox и др.),
                  десктопные мессенджеры и все браузеры целиком.
  --watch         Работает циклом в фоне и мгновенно завершается при закрытии stdin
                  (гарантирует отсутствие «подвисших» процессов после выхода из VS Code).
  --once          Выполнить один проход и выйти (для тестирования).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

SELF_PID = os.getpid()
PPID = os.getppid()

# ---------------------------------------------------------------------------
# Списки шаблонов (ИИ-чаты, VK, браузеры, игры)
# ---------------------------------------------------------------------------
BANNED_SITE_URL_RE = re.compile(
    r"(?:"
    r"chatgpt\.com|chat\.openai\.com|openai\.com/chatgpt|sora\.com|"
    r"deepseek\.com|chat\.deepseek\.com|"
    r"(?:alice|neuro)\.(?:yandex|ya)\.(?:ru|com)|(?:yandex|ya)\.ru/(?:ai|alice|chat|neuro)|shedevrum\.ai|"
    r"giga\.chat|gigachat\.sber\.ru|developers\.sber\.ru/.*gigachat|"
    r"claude\.ai|gemini\.google\.com|qwen\.ai|chat\.qwen\.ai|qwenlm\.ai|"
    r"perplexity\.ai|grok\.com|copilot\.microsoft\.com|poe\.com|chat\.mistral\.ai|"
    r"vk\.com|vk\.ru|vkvideo\.ru|vkplay\.ru|vkplay\.live|web\.vk\.me|vkontakte\.ru|"
    r"web\.telegram\.org|ok\.ru|discord\.com|web\.whatsapp\.com"
    r")",
    re.IGNORECASE,
)

# Заголовки вкладок/окон браузера: ловит и русские, и английские варианты названий,
# не затрагивая локальные страницы курса и документацию Python.
BANNED_SITE_TITLE_RE = re.compile(
    r"(?:"
    r"\bchatgpt\b|"
    r"\bchat\.openai\b|"
    r"\bdeepseek\b|"
    r"\bgigachat\b|гига\s*чат|"
    r"алиса\s*(?:ai|ии|нейро|gpt|чат)|чат\s+с\s+алисой|yandexgpt|alice\.yandex|"
    r"нейро\s*[-—|•]\s*яндекс|яндекс\s*нейро|[-—|•]\s*нейро(?:\s*[-—|•].*)?$|"
    r"(?:^|[-—|•]\s*)алиса(?:\s*\([^)]*\))?(?:\s*[-—|•].*)?$|"
    r"\bclaude\.ai\b|^claude(?:\s*[-—|•].*)?$|"
    r"^google\s+gemini|^gemini(?:\s*[-—|•].*)?$|"
    r"\bqwen\b|\bperplexity\b|^grok(?:\s*[-—|•].*)?$|"
    r"\bmicrosoft\s+copilot\b|^copilot\s*[-—|•]|"
    r"вконтакте|vkontakte|\bvk\.com\b|\bvk\.ru\b|"
    r"\bvk\s*(?:видео|музыка|клипы|мессенджер|play|video|music|clips)\b|"
    r"(?:^|\s|\||-|—)vk(?:\s*[-—|•].*|\s*)$|"
    r"^(?:новости|мессенджер|друзья|сообщества)(?:\s*\(\d+\))?(?:\s*[-—|•]\s*(?:google\s+chrome|chromium(?:-gost)?|yandex(?:\s+browser)?|яндекс(?:\s*\.?\s*браузер)?|mozilla\s+firefox|firefox|opera|microsoft\s+edge|edge|brave|vivaldi|sputnik).*)?$|"
    r"telegram\s+web|^telegram(?:\s*\(\d+\))?(?:\s*[-—|•].*)?$|"
    r"\bодноклассники\b|\bok\.ru\b|\bwhatsapp\b|\bdiscord\b"
    r")",
    re.IGNORECASE,
)

SAFE_TITLE_RE = re.compile(
    r"(?:пульт\s+учителя|localhost|127\.0\.0\.1|курс\s+«чат-боты|презентация|chrome://|about:)",
    re.IGNORECASE,
)

LINUX_BROWSER_EXES = {
    "chrome", "chromium", "chromium-browser", "chromium-gost", "google-chrome",
    "google-chrome-stable", "google-chrome-beta", "yandex-browser",
    "yandex-browser-stable", "yandex_browser", "firefox",
    "firefox-bin", "firefox-esr", "navigator", "opera", "msedge",
    "microsoft-edge", "brave", "brave-browser", "vivaldi", "vivaldi-bin",
    "sputnik", "atom-browser", "palemoon", "librewolf", "waterfox", "epiphany",
    "falkon", "konqueror", "midori", "qutebrowser",
}

LINUX_HARD_BLOCK_EXES = LINUX_BROWSER_EXES | {
    "telegram-desktop", "telegram-deskto", "telegram", "discord", "steam",
    "steamwebhelper", "minetest", "luanti", "supertux", "supertux2",
    "supertuxkart", "tlauncher", "minecraft", "minecraft-launcher", "minecraft-launc",
    "mcpelauncher-client", "mcpelauncher-ui", "modrinth-app", "gdlauncher-carbon",
    "klauncher", "prismlauncher", "polymc", "multimc", "gdlauncher",
    "atlauncher", "lutris", "heroic", "bottles", "robloxplayerbeta", "sober",
}

LINUX_BROWSER_CLASSES = (
    "chrome", "chromium", "google-chrome", "yandex", "firefox", "navigator",
    "opera", "msedge", "microsoft-edge", "brave", "vivaldi", "epiphany",
    "falkon", "konqueror", "palemoon", "librewolf", "waterfox", "tor",
    "midori", "qutebrowser", "sputnik", "atom", "crx_",
    "chatgpt", "deepseek", "vk.com", "vk.ru", "alice.yandex", "giga.chat", "gigachat",
)

JAVA_GAME_RE = re.compile(
    r"(?:minecraft|tlauncher|klauncher|curseforge|prismlauncher|polymc|multimc|mojang|optifine|fabricmc|minecraftforge)",
    re.IGNORECASE,
)

MINECRAFT_FLATPAK_RE = re.compile(
    r"\brun\b.*\b(?:com\.mojang\.Minecraft|org\.prismlauncher\.PrismLauncher|"
    r"io\.mrarm\.mcpelauncher|com\.modrinth\.ModrinthApp)(?=\s|$)",
    re.IGNORECASE,
)

WINE_GAME_RE = re.compile(
    r"(?:roblox|minecraft|tlauncher|steam|genshin|brawl|cs2|csgo|dota|valorant)",
    re.IGNORECASE,
)

WIN_BROWSER_EXES = {
    "chrome.exe", "msedge.exe", "browser.exe", "yandex.exe", "firefox.exe",
    "opera.exe", "brave.exe", "vivaldi.exe", "sputnik.exe", "atom.exe",
}

WIN_HARD_BLOCK_EXES = WIN_BROWSER_EXES | {
    "minecraft.exe", "minecraft.windows.exe", "minecraftlauncher.exe", "tlauncher.exe",
    "telegram.exe", "discord.exe", "steam.exe", "robloxplayerbeta.exe",
}

# Для отслеживания застрявших окон (если вкладку не удалось закрыть Ctrl+W — закрываем окно)
_seen_windows: dict[int, float] = {}


def is_banned_title(title: str) -> bool:
    if not title:
        return False
    if SAFE_TITLE_RE.search(title):
        return False
    return bool(BANNED_SITE_TITLE_RE.search(title) or BANNED_SITE_URL_RE.search(title))


# ---------------------------------------------------------------------------
# Linux: сканирование /proc + управление окнами X11 (ctypes libX11 / libXtst)
# ---------------------------------------------------------------------------
def _linux_read_procs() -> list[tuple[int, str, str, str]]:
    """Возвращает [(pid, comm, exe_name, cmdline_str)] без ограничения в 15 символов."""
    out: list[tuple[int, str, str, str]] = []
    uid = os.getuid()
    try:
        entries = os.listdir("/proc")
    except OSError:
        return out
    for name in entries:
        if not name.isdigit():
            continue
        pid = int(name)
        if pid <= 1 or pid == SELF_PID or pid == PPID:
            continue
        pdir = f"/proc/{name}"
        try:
            if os.stat(pdir).st_uid != uid:
                continue
            with open(f"{pdir}/comm", "r", encoding="utf-8", errors="ignore") as fh:
                comm = fh.read().strip().lower()
            with open(f"{pdir}/cmdline", "rb") as fh:
                raw = fh.read()
            parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\x00") if p]
            if not parts:
                continue
            exe_base = os.path.basename(parts[0]).lower()
            try:
                process_exe = os.path.basename(os.readlink(f"{pdir}/exe")).lower()
                exe_base = process_exe.removesuffix(" (deleted)") or exe_base
            except OSError:
                pass
            cmd_str = " ".join(parts)
            # Никогда не трогаем Python курса, сам редактор VS Code и терминал
            if exe_base in ("python", "python3") or exe_base.startswith(("python3.", "code", "codium")):
                continue
            out.append((pid, comm, exe_base, cmd_str))
        except OSError:
            continue
    return out


def _linux_kill_pwa_apps(procs: list[tuple[int, str, str, str]]) -> None:
    """Закрывает отдельные PWA/веб-приложения (--app=https://chatgpt.com и т.д.)."""
    for pid, comm, exe_base, cmd_str in procs:
        if ("--app=" in cmd_str or "--app-id=" in cmd_str) and BANNED_SITE_URL_RE.search(cmd_str):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        elif exe_base in ("telegram-desktop", "telegram", "discord", "chatgpt", "deepseek"):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


def _linux_kill_games_and_browsers(procs: list[tuple[int, str, str, str]]) -> None:
    """Жёсткий режим: закрывает игры, лаунчеры, мессенджеры и все браузеры."""
    for pid, comm, exe_base, cmd_str in procs:
        should_kill = False
        if exe_base in LINUX_HARD_BLOCK_EXES or comm in LINUX_HARD_BLOCK_EXES:
            should_kill = True
        elif exe_base.startswith("chromium") or exe_base.startswith("yandex") or exe_base.startswith("firefox"):
            should_kill = True
        elif {"java", "javaw"}.intersection((exe_base, comm)) and JAVA_GAME_RE.search(cmd_str):
            should_kill = True
        elif exe_base == "flatpak" and MINECRAFT_FLATPAK_RE.search(cmd_str):
            should_kill = True
        elif exe_base in ("wine", "wine64", "wine-preloader", "wine64-preloader") and WINE_GAME_RE.search(cmd_str):
            should_kill = True
        if should_kill:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


class _X11Helper:
    """Лёгкая обёртка над libX11.so.6 (и опционально libXtst.so.6) без внешних зависимостей."""

    def __init__(self) -> None:
        self.x11 = None
        self.xtst = None
        self.dpy = None
        self.root = 0
        self._err_cb = None
        if not os.environ.get("DISPLAY"):
            return
        for cand in ("libX11.so.6", "libX11.so", ctypes.util.find_library("X11")):
            if cand:
                try:
                    self.x11 = ctypes.CDLL(cand)
                    break
                except OSError:
                    pass
        if not self.x11:
            return
        for cand in ("libXtst.so.6", "libXtst.so", ctypes.util.find_library("Xtst")):
            if cand:
                try:
                    self.xtst = ctypes.CDLL(cand)
                    break
                except OSError:
                    pass
        self._setup_signatures()
        err_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self._err_cb = err_type(lambda _d, _e: 0)
        self.x11.XSetErrorHandler(self._err_cb)
        self.dpy = self.x11.XOpenDisplay(None)
        if self.dpy:
            self.root = self.x11.XDefaultRootWindow(self.dpy)
            self.a_client_list = self.x11.XInternAtom(self.dpy, b"_NET_CLIENT_LIST", False)
            self.a_active = self.x11.XInternAtom(self.dpy, b"_NET_ACTIVE_WINDOW", False)
            self.a_wm_name = self.x11.XInternAtom(self.dpy, b"_NET_WM_NAME", False)
            self.a_legacy_name = self.x11.XInternAtom(self.dpy, b"WM_NAME", False)
            self.a_wm_class = self.x11.XInternAtom(self.dpy, b"WM_CLASS", False)
            self.a_wm_pid = self.x11.XInternAtom(self.dpy, b"_NET_WM_PID", False)
            self.a_close = self.x11.XInternAtom(self.dpy, b"_NET_CLOSE_WINDOW", False)

    def _setup_signatures(self) -> None:
        x11 = self.x11
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XFree.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XFlush.restype = ctypes.c_int
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XSync.restype = ctypes.c_int
        x11.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        x11.XSetErrorHandler.restype = ctypes.c_void_p
        x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XKeysymToKeycode.restype = ctypes.c_uint
        x11.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
        x11.XSendEvent.restype = ctypes.c_int
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
            ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
        ]
        x11.XGetWindowProperty.restype = ctypes.c_int
        if self.xtst:
            self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
            self.xtst.XTestFakeKeyEvent.restype = ctypes.c_int

    def _get_prop(self, wid: int, atom: int) -> tuple[int, bytes | list[int] | None]:
        if not self.dpy or not wid or not atom:
            return 0, None
        actual_type = ctypes.c_ulong()
        actual_fmt = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop_ptr = ctypes.c_void_p()
        rc = self.x11.XGetWindowProperty(
            self.dpy, wid, atom, 0, 16384, 0, 0,
            ctypes.byref(actual_type), ctypes.byref(actual_fmt),
            ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(prop_ptr),
        )
        if rc != 0 or not prop_ptr.value:
            return 0, None
        try:
            fmt = actual_fmt.value
            cnt = nitems.value
            if cnt == 0:
                return fmt, None
            if fmt == 8:
                raw = ctypes.string_at(prop_ptr.value, cnt)
                return 8, raw
            if fmt == 32:
                # В Xlib формат 32 всегда распаковывается в массив c_ulong
                arr = ctypes.cast(prop_ptr.value, ctypes.POINTER(ctypes.c_ulong))
                return 32, [int(arr[i]) for i in range(cnt)]
            return fmt, None
        finally:
            self.x11.XFree(prop_ptr)

    def active_window(self) -> int:
        fmt, vals = self._get_prop(self.root, self.a_active)
        if fmt == 32 and isinstance(vals, list) and vals:
            return vals[0]
        return 0

    def list_windows(self) -> list[tuple[int, str, str, int]]:
        """Возвращает [(wid, wm_class, title, pid)]."""
        fmt, wids = self._get_prop(self.root, self.a_client_list)
        if fmt != 32 or not isinstance(wids, list):
            return []
        res: list[tuple[int, str, str, int]] = []
        for wid in wids:
            _, cls_raw = self._get_prop(wid, self.a_wm_class)
            wm_class = ""
            if isinstance(cls_raw, bytes):
                wm_class = cls_raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip().lower()
            _, name_raw = self._get_prop(wid, self.a_wm_name)
            if not isinstance(name_raw, bytes):
                _, name_raw = self._get_prop(wid, self.a_legacy_name)
            title = name_raw.decode("utf-8", errors="ignore").strip() if isinstance(name_raw, bytes) else ""
            _, pid_vals = self._get_prop(wid, self.a_wm_pid)
            pid = pid_vals[0] if isinstance(pid_vals, list) and pid_vals else 0
            res.append((wid, wm_class, title, pid))
        return res

    def send_ctrl_w(self, expected_wid: int) -> bool:
        """Отправляет физический Ctrl+W (независимо от русской раскладки), только если окно активно."""
        if not self.xtst or not self.dpy:
            return False
        if self.active_window() != expected_wid:
            return False
        ctrl_kc = self.x11.XKeysymToKeycode(self.dpy, 0xFFE3)  # XK_Control_L
        w_kc = self.x11.XKeysymToKeycode(self.dpy, 0x0077)     # XK_w
        if not ctrl_kc or not w_kc:
            return False
        if self.active_window() != expected_wid:
            return False
        self.xtst.XTestFakeKeyEvent(self.dpy, ctrl_kc, 1, 0)
        self.xtst.XTestFakeKeyEvent(self.dpy, w_kc, 1, 0)
        self.xtst.XTestFakeKeyEvent(self.dpy, w_kc, 0, 0)
        self.xtst.XTestFakeKeyEvent(self.dpy, ctrl_kc, 0, 0)
        self.x11.XFlush(self.dpy)
        return True

    def close_window(self, wid: int) -> None:
        if not self.dpy or not wid:
            return

        class _ClientMsg(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_int),
                ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong),
                ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int),
                ("l", ctypes.c_long * 5),
            ]

        class _XEventPad(ctypes.Union):
            _fields_ = [("msg", _ClientMsg), ("pad", ctypes.c_long * 24)]

        ev = _XEventPad()
        ev.msg.type = 33  # ClientMessage
        ev.msg.send_event = 1
        ev.msg.display = self.dpy
        ev.msg.window = wid
        ev.msg.message_type = self.a_close
        ev.msg.format = 32
        ev.msg.l[0] = 0
        ev.msg.l[1] = 1
        mask = (1 << 20) | (1 << 19)  # SubstructureRedirectMask | SubstructureNotifyMask
        self.x11.XSendEvent(self.dpy, self.root, 0, mask, ctypes.byref(ev))
        self.x11.XFlush(self.dpy)


_x11: _X11Helper | None = None


def _linux_enforce_browser_sites(procs: list[tuple[int, str, str, str]]) -> None:
    global _x11
    _linux_kill_pwa_apps(procs)
    if _x11 is None:
        _x11 = _X11Helper()
    if not _x11.dpy:
        return
    now = time.time()
    active_wid = _x11.active_window()
    safe_kill_pids = {
        pid: exe_base
        for pid, comm, exe_base, _ in procs
        if exe_base in LINUX_BROWSER_EXES or comm in LINUX_BROWSER_EXES
        or exe_base.startswith(("chromium", "yandex", "firefox"))
    }
    alive_wids: set[int] = set()
    for wid, wm_class, title, pid in _x11.list_windows():
        if not title:
            continue
        # Исключаем VS Code и терминалы, проверяем только окна браузеров и PWA
        is_browser_win = any(c in wm_class for c in LINUX_BROWSER_CLASSES)
        if not is_browser_win:
            continue
        if not is_banned_title(title):
            continue
        alive_wids.add(wid)
        first_seen = _seen_windows.get(wid)
        if first_seen is None:
            _seen_windows[wid] = now
            # 1-й шаг: если окно активно прямо сейчас — пробуем тихо закрыть только вкладку Ctrl+W
            if wid == active_wid and _x11.send_ctrl_w(wid):
                continue
            # Если окно в фоне (рядом с VS Code) или Ctrl+W недоступен — закрываем само окно браузера
            _x11.close_window(wid)
        elif now - first_seen < 2.2:
            # 2-й шаг: окно ещё не закрылось (например, диалог «Закрыть вкладки?») — закрываем окно
            _x11.close_window(wid)
        else:
            # 3-й шаг: окно упорно не закрывается — принудительно завершаем процесс браузера
            if pid and pid in safe_kill_pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            else:
                _x11.close_window(wid)
    # Чистим закрытые окна из истории
    for old_wid in list(_seen_windows):
        if old_wid not in alive_wids:
            _seen_windows.pop(old_wid, None)


# ---------------------------------------------------------------------------
# Windows: ctypes user32 + kernel32 / taskkill
# ---------------------------------------------------------------------------
_win_apis_configured = False


def _win_setup_apis(user32: ctypes.WinDLL, kernel32: ctypes.WinDLL, wndenumproc: type) -> None:
    global _win_apis_configured
    if _win_apis_configured:
        return
    from ctypes import wintypes

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.EnumWindows.argtypes = [wndenumproc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
    user32.keybd_event.restype = None
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    _win_apis_configured = True


def _win_kill_java_games() -> None:
    """На Windows завершает только те процессы javaw.exe/java.exe, чей командлайн совпадает с JAVA_GAME_RE."""
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='javaw.exe' OR Name='java.exe'\" "
        "| ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            creationflags=0x08000000,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    pids: list[str] = []
    for line in (res.stdout or "").splitlines():
        if "\t" not in line:
            continue
        pid_str, cmdline = line.split("\t", 1)
        pid_str = pid_str.strip()
        if pid_str.isdigit() and JAVA_GAME_RE.search(cmdline):
            pid_int = int(pid_str)
            if pid_int != SELF_PID and pid_int != PPID:
                pids.append(pid_str)
    if pids:
        args = ["taskkill", "/F"]
        for pid_str in pids:
            args.extend(["/PID", pid_str])
        try:
            subprocess.run(args, creationflags=0x08000000, capture_output=True, timeout=4, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _win_enforce(block_games: bool, block_sites: bool) -> None:
    if block_games:
        args = ["taskkill", "/F", "/T"]
        for exe in WIN_HARD_BLOCK_EXES:
            args.extend(["/IM", exe])
        try:
            subprocess.run(args, creationflags=0x08000000, capture_output=True, timeout=4, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        _win_kill_java_games()
        return

    if not block_sites:
        return

    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _win_setup_apis(user32, kernel32, WNDENUMPROC)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    WM_CLOSE = 0x0010
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_W = 0x57
    KEYEVENTF_KEYUP = 0x0002

    fg_hwnd = int(user32.GetForegroundWindow() or 0)
    matched_windows: list[tuple[int, int, str]] = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not is_banned_title(title):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == SELF_PID or pid.value == PPID:
            return True
        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        exe_name = ""
        if hproc:
            try:
                pbuf = ctypes.create_unicode_buffer(512)
                psize = wintypes.DWORD(512)
                if kernel32.QueryFullProcessImageNameW(hproc, 0, pbuf, ctypes.byref(psize)):
                    exe_name = os.path.basename(pbuf.value).lower()
            finally:
                kernel32.CloseHandle(hproc)
        if exe_name in WIN_BROWSER_EXES:
            matched_windows.append((int(hwnd), int(pid.value), title))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    now = time.time()
    alive: set[int] = set()
    for hwnd, pid, _title in matched_windows:
        alive.add(hwnd)
        first_seen = _seen_windows.get(hwnd)
        if first_seen is None:
            _seen_windows[hwnd] = now
            if hwnd == fg_hwnd and int(user32.GetForegroundWindow() or 0) == hwnd:
                # Отпускаем Shift, если ученик держал его (иначе Ctrl+Shift+W закроет всё окно)
                if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
                    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
                # Повторная проверка фокуса прямо перед отправкой Ctrl+W
                if int(user32.GetForegroundWindow() or 0) == hwnd:
                    # Ctrl+W через виртуальный код W (0x57) работает и при русской раскладке
                    user32.keybd_event(VK_CONTROL, 0, 0, 0)
                    user32.keybd_event(VK_W, 0, 0, 0)
                    user32.keybd_event(VK_W, 0, KEYEVENTF_KEYUP, 0)
                    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
                else:
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            else:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        elif now - first_seen < 2.2:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        else:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    creationflags=0x08000000,
                    capture_output=True,
                    timeout=4,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
    for old in list(_seen_windows):
        if old not in alive:
            _seen_windows.pop(old, None)


# ---------------------------------------------------------------------------
# macOS: JXA (прямая проверка URL и заголовков вкладок браузеров) + pkill
# ---------------------------------------------------------------------------
_JXA_CLOSE_TABS = r"""
ObjC.import('stdlib');
const BANNED_URL = /(?:chatgpt\.com|chat\.openai\.com|openai\.com\/chatgpt|sora\.com|deepseek\.com|chat\.deepseek\.com|(?:alice|neuro)\.(?:yandex|ya)\.(?:ru|com)|(?:yandex|ya)\.ru\/(?:ai|alice|chat|neuro)|shedevrum\.ai|giga\.chat|gigachat\.sber\.ru|developers\.sber\.ru\/.*gigachat|claude\.ai|gemini\.google\.com|qwen\.ai|chat\.qwen\.ai|qwenlm\.ai|perplexity\.ai|grok\.com|copilot\.microsoft\.com|poe\.com|chat\.mistral\.ai|vk\.com|vk\.ru|vkvideo\.ru|vkplay\.ru|vkplay\.live|web\.vk\.me|vkontakte\.ru|web\.telegram\.org|ok\.ru|discord\.com|web\.whatsapp\.com)/i;
const BANNED_TITLE = /(?:\bchatgpt\b|\bchat\.openai\b|\bdeepseek\b|\bgigachat\b|гига\s*чат|алиса\s*(?:ai|ии|нейро|gpt|чат)|чат\s+с\s+алисой|yandexgpt|alice\.yandex|нейро\s*[-—|•]\s*яндекс|яндекс\s*нейро|[-—|•]\s*нейро(?:\s*[-—|•].*)?$|(?:^|[-—|•]\s*)алиса(?:\s*\([^)]*\))?(?:\s*[-—|•].*)?$|\bclaude\.ai\b|^claude(?:\s*[-—|•].*)?$|^google\s+gemini|^gemini(?:\s*[-—|•].*)?$|\bqwen\b|\bperplexity\b|^grok(?:\s*[-—|•].*)?$|\bmicrosoft\s+copilot\b|^copilot\s*[-—|•]|вконтакте|vkontakte|\bvk\.com\b|\bvk\.ru\b|\bvk\s*(?:видео|музыка|клипы|мессенджер|play|video|music|clips)\b|(?:^|\s|\||-|—)vk(?:\s*[-—|•].*|\s*)$|^(?:новости|мессенджер|друзья|сообщества)(?:\s*\(\d+\))?(?:\s*[-—|•]\s*(?:google\s+chrome|chromium(?:-gost)?|yandex(?:\s+browser)?|яндекс(?:\s*\.?\s*браузер)?|mozilla\s+firefox|firefox|opera|microsoft\s+edge|edge|brave|vivaldi|sputnik|safari).*)?$|telegram\s+web|^telegram(?:\s*\(\d+\))?(?:\s*[-—|•].*)?$|\bодноклассники\b|\bok\.ru\b|\bwhatsapp\b|\bdiscord\b)/i;
const SAFE = /(?:пульт\s+учителя|localhost|127\.0\.0\.1|курс\s+«чат-боты|презентация|chrome:\/\/|about:|gemini api)/i;

function bad(url, title) {
  const u = String(url || '');
  const t = String(title || '');
  if (SAFE.test(u) || SAFE.test(t)) return false;
  return BANNED_URL.test(u) || BANNED_TITLE.test(t);
}

const se = Application('System Events');
const running = new Set(se.processes.whose({ backgroundOnly: false }).name().map(n => String(n)));

const chromiumBrowsers = ['Google Chrome', 'Chromium', 'Yandex', 'Microsoft Edge', 'Brave Browser', 'Opera', 'Vivaldi'];
for (const name of chromiumBrowsers) {
  if (!running.has(name)) continue;
  try {
    const app = Application(name);
    for (const w of app.windows()) {
      const tabs = w.tabs();
      for (let i = tabs.length - 1; i >= 0; i--) {
        const t = tabs[i];
        if (bad(t.url(), t.title())) t.close();
      }
    }
  } catch (e) {}
}
if (running.has('Safari')) {
  try {
    const saf = Application('Safari');
    for (const w of saf.windows()) {
      const tabs = w.tabs();
      for (let i = tabs.length - 1; i >= 0; i--) {
        const t = tabs[i];
        if (bad(t.url(), t.name())) t.close();
      }
    }
  } catch (e) {}
}
if (running.has('Firefox')) {
  try {
    const ff = se.processes.byName('Firefox');
    for (const w of ff.windows()) {
      if (bad('', w.name())) {
        const btns = w.buttons.whose({ subrole: 'AXCloseButton' });
        if (btns.length) btns[0].click();
      }
    }
  } catch (e) {}
}
"""


def _mac_enforce(block_games: bool, block_sites: bool) -> None:
    if block_games:
        names = [
            "Google Chrome", "Chromium", "Yandex", "firefox", "Opera",
            "Microsoft Edge", "Brave Browser", "Vivaldi", "Safari",
            "Telegram", "Discord", "Steam", "TLauncher",
        ]
        try:
            subprocess.run(["pkill", "-x", "|".join(names)], capture_output=True, timeout=4, check=False)
            subprocess.run(
                ["pkill", "-f", "-i", "(java|javaw).*(minecraft|tlauncher|klauncher|curseforge|prism)"],
                capture_output=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        return
    if block_sites and shutil.which("osascript"):
        try:
            subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", _JXA_CLOSE_TABS],
                capture_output=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass


# ---------------------------------------------------------------------------
# Главный шаг и цикл наблюдения
# ---------------------------------------------------------------------------
def step(block_games: bool, block_sites: bool) -> None:
    if sys.platform.startswith("linux"):
        procs = _linux_read_procs()
        if block_games:
            _linux_kill_games_and_browsers(procs)
        elif block_sites:
            _linux_enforce_browser_sites(procs)
    elif os.name == "nt":
        _win_enforce(block_games, block_sites)
    elif sys.platform == "darwin":
        _mac_enforce(block_games, block_sites)


def _watch_stdin_eof() -> None:
    """Как только VS Code закроется или упадёт — stdin закроется и мы сразу завершимся."""
    try:
        while sys.stdin.read(1024):
            pass
    except Exception:
        pass
    os._exit(0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Focus & browser site guard")
    ap.add_argument("--block-games", action="store_true")
    ap.add_argument("--block-sites", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=1.5 if sys.platform == "darwin" else 0.9)
    a = ap.parse_args(argv)
    if not (a.block_games or a.block_sites):
        return 0
    if a.once or not a.watch:
        step(a.block_games, a.block_sites)
        return 0
    t = threading.Thread(target=_watch_stdin_eof, daemon=True)
    t.start()
    min_interval = 1.5 if sys.platform == "darwin" else 0.3
    while True:
        try:
            step(a.block_games, a.block_sites)
        except Exception:
            pass
        time.sleep(max(min_interval, a.interval))


if __name__ == "__main__":
    raise SystemExit(main())
