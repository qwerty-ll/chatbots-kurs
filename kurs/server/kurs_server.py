#!/usr/bin/env python3
"""Сервер курса «Чат-боты на Python».

Работает на учительском ПК только в дни занятий. Нужна только стандартная библиотека Python 3.8+.

  python3 kurs_server.py                    запустить (порт 8000, данные в ~/.kurs-server)
  python3 kurs_server.py --port 8080        другой порт
  python3 kurs_server.py --data /srv/kurs   другая папка с данными
  python3 kurs_server.py --reset-password   забыть пароль учителя (задать новый на странице)

Страница учителя: http://localhost:8000/teacher (открывается только на этом компьютере).
Остановить сервер: Ctrl+C.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import errno
import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
import zipfile
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import kurs_ai
import kurs_play

HERE = os.path.dirname(os.path.abspath(__file__))
KURS = os.path.dirname(HERE)
REPO = os.path.dirname(KURS)
AI_LOG_DAYS = 30               # сколько дней хранить ленту вопросов к нейросети
VERSION = "0.1.0"

MAX_BODY = 512 * 1024          # байт в одном запросе
MAX_FILE = 100 * 1024          # байт в одном файле ученика
MAX_FILES = 60                 # файлов в одной отправке
ONLINE_SEC = 15                # ученик «на связи», если писал не позже стольких секунд назад
LOCAL = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL, name TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, student_id INTEGER NOT NULL, pc TEXT NOT NULL,
    started REAL NOT NULL, seen REAL NOT NULL, closed REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, secret TEXT NOT NULL, kind TEXT NOT NULL,
    student_id INTEGER NOT NULL, pc TEXT NOT NULL, prev_student_id INTEGER, other_pc TEXT,
    status TEXT NOT NULL, created REAL NOT NULL, token TEXT);
CREATE TABLE IF NOT EXISTS results(student_id INTEGER NOT NULL, task_id TEXT NOT NULL, status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0, hints INTEGER NOT NULL DEFAULT 0, rating TEXT, summary TEXT, code TEXT,
    updated REAL NOT NULL, PRIMARY KEY(student_id, task_id));
CREATE TABLE IF NOT EXISTS help(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, pc TEXT, text TEXT,
    status TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS files(student_id INTEGER NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL,
    updated REAL NOT NULL, PRIMARY KEY(student_id, path));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts REAL NOT NULL, student_id INTEGER, kind TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ai_log(id INTEGER PRIMARY KEY, ts REAL NOT NULL, student_id INTEGER, pc TEXT,
    question TEXT, system TEXT, answer TEXT, status TEXT, ms INTEGER, cached INTEGER, flags TEXT);
CREATE TABLE IF NOT EXISTS ideas(student_id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', about TEXT NOT NULL DEFAULT '',
    tools TEXT NOT NULL DEFAULT '', updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL, name TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '', bot_name TEXT NOT NULL DEFAULT '', persona TEXT NOT NULL DEFAULT '',
    banned TEXT NOT NULL DEFAULT '[]', edited_by TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_members(student_id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL,
    plan TEXT NOT NULL DEFAULT '', joined REAL NOT NULL);
"""

DEFAULT_STATE = {"running": 0, "group_id": None, "lesson": 2, "open_tasks": [], "paused": 0, "pause_text": "",
                 "timer_end": None, "timer_label": "", "stage": 0, "class_id": 0, "restart_seq": 0, "close_seq": 0,
                 "lock_on_paste": 1, "locks": {},
                 "play": {"mode": "off", "games": ["chess", "hockey", "battleship"], "teacher": True, "allow": []},
                 "teams": {"open": True, "min": 2, "max": 0}, "team_notices": {},
                 "last_class": None}
MAX_TEAMS = 30                 # команд в одной группе
IDEA_LIMITS = {"title": 80, "about": 400, "tools": 400}
TEAM_LIMITS = {"topic": 120, "bot_name": 40, "persona": 400}


# ---------------------------------------------------------------------------
# Материалы: занятия и задания (папка kurs/tasks)
# ---------------------------------------------------------------------------
class Library:
    def __init__(self, tasks_dir: str, content_dir: str):
        self.tasks_dir = tasks_dir
        self.content_dir = content_dir
        self.load()

    def load(self) -> None:
        self.lessons: dict[int, dict] = {}
        self.tasks: dict[str, dict] = {}
        for name in sorted(os.listdir(self.tasks_dir)):
            ldir = os.path.join(self.tasks_dir, name)
            lfile = os.path.join(ldir, "lesson.json")
            if not os.path.isfile(lfile):
                continue
            lesson = _read_json(lfile)
            lesson["task_ids"] = []
            for sub in sorted(os.listdir(ldir)):
                tfile = os.path.join(ldir, sub, "task.json")
                if not os.path.isfile(tfile):
                    continue
                t = _read_json(tfile)
                t["_dir"] = os.path.join(ldir, sub)
                t["_start"] = _read(os.path.join(ldir, sub, "start.py"))
                t["_solution"] = _read(os.path.join(ldir, sub, "solution.py"))
                self.tasks[t["id"]] = t
                lesson["task_ids"].append(t["id"])
            lesson["_files"] = {}
            for name, rel in (lesson.get("files") or {}).items():
                path = os.path.normpath(os.path.join(REPO, rel))
                if path.startswith(REPO + os.sep) and os.path.isfile(path):
                    lesson["_files"][name] = _read(path)
            nb = os.path.join(ldir, "notebook.py")
            lesson["_notebook"] = _read(nb) if os.path.isfile(nb) else ""
            lesson["stages"] = notebook_stages(lesson["_notebook"])
            self.lessons[lesson["lesson"]] = lesson
        cs = os.path.join(self.content_dir, "cheatsheet.json")
        self.cheatsheet = _read_json(cs) if os.path.isfile(cs) else {"sections": []}

    def public_task(self, t: dict, with_start: bool = True) -> dict:
        d = {k: v for k, v in t.items() if not k.startswith("_") and k != "hints"}
        d["hints_count"] = len(t.get("hints", []))
        if with_start:
            d["start"] = t["_start"]
        return d


def notebook_stages(text: str) -> list[dict]:
    stages = []
    for i, ln in enumerate(text.splitlines()):
        m = re.match(r"^#\s*ЭТАП\s+(\d+)\s*:\s*(.*)$", ln)
        if m:
            stages.append({"n": int(m.group(1)), "title": m.group(2).strip(), "line": i})
    return stages


def notebook_upto(text: str, n: int) -> str:
    """Код тетради с первого этапа по этап n включительно."""
    lines = text.splitlines()
    st = notebook_stages(text)
    if not st:
        return text
    start = st[0]["line"]
    end = len(lines)
    for s in st:
        if s["n"] == n + 1:
            end = s["line"]
    return "\n".join(lines[start:end]).rstrip() + "\n"


def training_template(lesson: dict) -> str:
    n = lesson.get("lesson", 1)
    title = lesson.get("title", "")
    header = [
        "# =====================================================================",
        f"# 🧪 ПОЛЕ ТРЕНИРОВКИ И ЭКСПЕРИМЕНТОВ: Урок {n}. {title}",
        "# =====================================================================",
        "# Здесь можно свободно писать любой код, пробовать команды и проверять идеи!",
        "# Запуск файла: кнопка «▶ Запустить тренировку» в панели или треугольник вверху.",
        "# =====================================================================",
        "",
    ]
    if n == 1:
        body = [
            "# 1. Вывод текста на экран:",
            'print("Привет! Я тренируюсь писать код на Python.")',
            "",
            "# 2. Ввод данных от пользователя (input всегда возвращает строку):",
            'name = input("Как тебя зовут? ")',
            'print(f"Приятно познакомиться, {name}!")',
            "",
            "# 3. Числа и вычисления (int превращает текст из input в целое число):",
            'age = int(input("Сколько тебе лет? "))',
            'print(f"Через 5 лет тебе будет {age + 5} лет!")',
            "",
            "# 4. Условие if / else (не забывай двоеточие : и отступ в 4 пробела!):",
            'if age >= 18:',
            '    print("Ты совершеннолетний!")',
            'else:',
            '    print("У тебя всё впереди!")',
        ]
    elif n == 2:
        body = [
            "# 1. Списки (коллекции команд и слов):",
            'commands = ["привет", "помощь", "погода", "пока"]',
            'print("Список команд бота:", commands)',
            "",
            "# 2. Проверка наличия в списке через 'in':",
            'msg = input("Введи команду: ").lower()',
            'if msg in commands:',
            '    print(f"Команда «{msg}» принята в работу!")',
            'else:',
            '    print("Неизвестная команда. Попробуй ещё раз.")',
            "",
            "# 3. Цикл for для перебора элементов:",
            'for cmd in commands:',
            '    print("Доступно:", cmd)',
        ]
    elif n == 3:
        body = [
            "# 1. Подключение нейросети курса одной строкой:",
            'from ai import ask',
            "",
            "# 2. Простой вопрос к нейросети:",
            'print("Спрашиваю нейросеть…")',
            'answer = ask("Расскажи очень короткий забавный факт о котиках")',
            'print("Ответ нейросети:")',
            'print(answer)',
            "",
            "# 3. Интерактивный вопрос от пользователя:",
            'user_query = input("О чём спросить ИИ? ")',
            'if user_query.strip():',
            '    print(ask(user_query))',
            "",
            "# 💡 ПОДСКАЗКА:",
            "# Если видишь NameError: name 'ask' is not defined — проверь первую строку: from ai import ask",
        ]
    elif n == 4:
        body = [
            "# 1. Роли и системный промпт (задаём характер нейросети):",
            'from ai import ask',
            "",
            'pirate = ask("Как погода?", role="Ты старый морской пират. Отвечай с пиратским акцентом.")',
            'print("Пират:")',
            'print(pirate)',
            "",
            "# 2. Температура ответа (temperature):",
            '# 0.1–0.3 — строгий и точный ответ (для фактов и математики)',
            '# 0.7–1.0 — творческий и образный ответ (для историй и игр)',
            'fact = ask("Сколько океанов на Земле?", temperature=0.1)',
            'print("Точный факт:", fact)',
        ]
    elif n == 5:
        body = [
            "# 1. Функция: def создаёт, return отдаёт результат:",
            'import random',
            "",
            "",
            'def roll_dice(sides=6):',
            '    return random.randint(1, sides)',
            "",
            "",
            'print("Кубик:", roll_dice(), "· кубик на 20:", roll_dice(20))',
            "",
            "# 2. Инструмент = функция + описание для нейросети + строчка в словаре функций:",
            'from agent import agent_answer, make_tool',
            "",
            'TOOLS = [make_tool("roll_dice", "Бросить игральный кубик.",',
            '                   {"sides": {"type": "integer", "description": "Число граней"}})]',
            'FUNCTIONS = {"roll_dice": lambda args: roll_dice(args.get("sides", 6))}',
            "",
            "# 3. Агент сам решает, когда звать инструмент (строки 🔧 — вызовы):",
            'messages = [{"role": "user", "content": "Брось кубик на 12 граней"}]',
            'print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))',
        ]
    elif n == 6:
        body = [
            "# Здесь можно пробовать идеи для своих инструментов, не трогая Мои_инструменты.py.",
            'import random',
            "",
            "",
            'def fact():',
            '    return random.choice(["У осьминога три сердца.", "Мёд не портится тысячи лет."])',
            "",
            "",
            'print(fact())',
            "",
            "# Весь бот команды — файл Наш_бот.py: он сам соберёт инструменты всех участников.",
        ]
    else:
        body = [
            "# Итоговый проект:",
            'from ai import ask, chat',
            "",
            'print("Мой чат-бот запущен!")',
            '# Пиши свой код здесь.',
        ]
    return "\n".join(header + body) + "\n"


notebook_template = training_template


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_json(path: str):
    return json.loads(_read(path))


# ---------------------------------------------------------------------------
# Хранилище
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        try:
            os.chmod(data_dir, 0o700)   # данные детей: читает только пользователь сервера
        except OSError:
            pass
        self.data_dir = data_dir
        self.db = sqlite3.connect(os.path.join(data_dir, "kurs.sqlite3"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.teacher_tokens: dict[str, float] = {}

    # --- state ---
    def get(self, key: str):
        r = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else DEFAULT_STATE.get(key)

    def set(self, key: str, value) -> None:
        self.db.execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value, ensure_ascii=False)))

    def state(self) -> dict:
        return {k: self.get(k) for k in DEFAULT_STATE}

    def q(self, sql: str, args=()):
        return self.db.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        return self.db.execute(sql, args).fetchone()

    def ex(self, sql: str, args=()):
        return self.db.execute(sql, args)

    def log(self, student_id, kind: str, data=None) -> None:
        self.ex("INSERT INTO events(ts,student_id,kind,data) VALUES(?,?,?,?)",
                (time.time(), student_id, kind, json.dumps(data, ensure_ascii=False) if data is not None else None))

    # --- пароль учителя ---
    def password_file(self) -> str:
        return os.path.join(self.data_dir, "teacher_password.json")

    def has_password(self) -> bool:
        return os.path.isfile(self.password_file())

    def set_password(self, pw: str) -> None:
        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
        with open(self.password_file(), "w", encoding="utf-8") as fh:
            json.dump({"salt": salt.hex(), "hash": h.hex()}, fh)
        try:
            os.chmod(self.password_file(), 0o600)
        except OSError:
            pass

    def check_password(self, pw: str) -> bool:
        if not self.has_password():
            return False
        d = _read_json(self.password_file())
        h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(d["salt"]), 200_000)
        return hmac.compare_digest(h.hex(), d["hash"])


# ---------------------------------------------------------------------------
# Логика курса
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra or {}


class Kurs:
    def __init__(self, store: Store, lib: Library):
        self.s = store
        self.lib = lib
        self.ai = kurs_ai.Gateway(store.data_dir, log_fn=self.ai_log)
        self.play = kurs_play.Play()
        with store.lock:
            store.ex("DELETE FROM ai_log WHERE ts < ?", (time.time() - AI_LOG_DAYS * 86400,))
            store.db.commit()

    # ---------- нейросеть ----------
    def ai_log(self, t, ms: int) -> None:
        """Запись в ленту учителя: кто что спросил и что ответила нейросеть."""
        question = next((m["content"] for m in reversed(t.messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in t.messages if m["role"] == "system"), "")
        system = system.replace(kurs_ai.SHORT_HINT, "").replace(kurs_ai.NO_CODE_HINT, "").strip()
        answer = (t.message or {}).get("content") if t.status == "done" else t.error
        if t.status == "done" and (t.message or {}).get("tool_calls"):
            answer = "🔧 " + ", ".join(c["function"]["name"] for c in t.message["tool_calls"])
        with self.s.lock:
            self.s.ex("INSERT INTO ai_log(ts,student_id,pc,question,system,answer,status,ms,cached,flags) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (time.time(), t.student_id, t.pc, question[:4000], system[:1000], (answer or "")[:4000], t.status, ms,
                       1 if t.cached else 0, ",".join(kurs_ai.flags_for(question))))
            self.s.db.commit()

    def ai_ask(self, sess, body: dict) -> dict:
        today = self.s.one("SELECT COUNT(*) AS n FROM ai_log WHERE student_id=? AND ts>=?", (sess["student_id"], _day_start()))["n"]
        try:
            t = self.ai.ask(sess["student_id"], self.name(sess["student_id"]), sess["pc"], body.get("messages"),
                            body.get("temperature", 0.7), body.get("max_tokens", 1500), body.get("tools"), today,
                            allow_code=bool(body.get("allow_code")))
        except kurs_ai.AIError as e:
            raise ApiError(429, str(e), {"retry_after": e.retry_after} if e.retry_after else None) from None
        return {"ticket": t.id}

    def ai_ticket(self, sess, tid: int) -> dict:
        try:
            return self.ai.ticket(tid, sess["student_id"])
        except kurs_ai.AIError as e:
            raise ApiError(404, str(e)) from None

    def ai_overview(self, student_id=None) -> dict:
        names = {r["id"]: r["name"] for r in self.s.q("SELECT id, name FROM students")}
        sql = "SELECT * FROM ai_log" + (" WHERE student_id=?" if student_id else "") + " ORDER BY id DESC LIMIT 500"
        rows = self.s.q(sql, (student_id,) if student_id else ())
        log = [{"id": r["id"], "ts": r["ts"], "student_id": r["student_id"], "name": names.get(r["student_id"], "?"), "pc": r["pc"],
                "question": r["question"], "system": r["system"], "answer": r["answer"], "status": r["status"],
                "ms": r["ms"], "cached": bool(r["cached"]), "flags": [f for f in (r["flags"] or "").split(",") if f]} for r in rows]
        today = self.s.one("SELECT COUNT(*) AS n FROM ai_log WHERE ts>=?", (_day_start(),))["n"]
        return {"status": self.ai.status(), "config": self.ai.public_config(), "log": log, "today": today}

    # ---------- помощники ----------
    def student(self, sid):
        return self.s.one("SELECT * FROM students WHERE id=?", (sid,))

    def name(self, sid) -> str:
        r = self.student(sid)
        return r["name"] if r else "?"

    def active_session_on_pc(self, pc: str):
        return self.s.one("SELECT * FROM sessions WHERE pc=? AND closed IS NULL ORDER BY started DESC", (pc,))

    def active_session_of(self, sid):
        return self.s.one("SELECT * FROM sessions WHERE student_id=? AND closed IS NULL ORDER BY started DESC", (sid,))

    def close_session(self, token: str, reason: str) -> None:
        self.s.ex("UPDATE sessions SET closed=?, reason=? WHERE token=? AND closed IS NULL", (time.time(), reason, token))

    def session_by_token(self, token: str | None):
        if not token:
            raise ApiError(401, "Нужно войти")
        r = self.s.one("SELECT * FROM sessions WHERE token=?", (token,))
        if not r:
            raise ApiError(401, "Нужно войти")
        return r

    def live_session(self, token: str | None):
        r = self.session_by_token(token)
        if r["closed"] is not None:
            raise ApiError(410, r["reason"] or "Сеанс закрыт")
        self.s.ex("UPDATE sessions SET seen=? WHERE token=?", (time.time(), token))
        return r

    def lesson(self) -> dict:
        n = self.s.get("lesson")
        if n not in self.lib.lessons:
            raise ApiError(404, "Занятие не найдено")
        return self.lib.lessons[n]

    def task(self, task_id: str, must_be_open: bool = True) -> dict:
        t = self.lib.tasks.get(task_id)
        if not t or t["lesson"] != self.s.get("lesson"):
            raise ApiError(404, "Нет такого задания")
        if must_be_open and task_id not in self.s.get("open_tasks"):
            raise ApiError(403, "Учитель ещё не открыл это задание")
        return t

    # ---------- вход ученика ----------
    def hello(self, pc: str) -> dict:
        st = self.s.state()
        out = {"server": VERSION, "running": bool(st["running"]), "pc": pc, "restart": st["restart_seq"],
               "close": st["close_seq"]}
        if not st["running"]:
            return out
        lesson = self.lib.lessons.get(st["lesson"], {})
        out.update(lesson=st["lesson"], title=lesson.get("title", ""))
        group = self.s.one("SELECT * FROM groups WHERE id=?", (st["group_id"],))
        out["group"] = group["name"] if group else ""
        students = []
        for r in self.s.q("SELECT * FROM students WHERE group_id=? AND archived=0 ORDER BY name", (st["group_id"],)):
            sess = self.active_session_of(r["id"])
            students.append({"id": r["id"], "name": r["name"], "pc": sess["pc"] if sess else None})
        out["students"] = students
        here = self.active_session_on_pc(pc)
        if here:
            out["here"] = {"student_id": here["student_id"], "name": self.name(here["student_id"])}
        return out

    def login(self, pc: str, sid: int) -> dict:
        if not self.s.get("running"):
            raise ApiError(409, "Занятие ещё не началось. Подожди учителя.")
        st = self.student(sid)
        if not st or st["group_id"] != self.s.get("group_id") or st["archived"]:
            raise ApiError(404, "Такого ученика нет в группе")
        mine = self.active_session_of(sid)
        if mine and mine["pc"] == pc:
            # тот же ученик за тем же ПК (например, после перезагрузки): подтверждение не нужно
            return {"status": "approved", "token": mine["token"], "name": st["name"], "student_id": sid}
        here = self.active_session_on_pc(pc)
        if here:
            kind, prev, other = "switch", here["student_id"], None
        elif mine:
            kind, prev, other = "transfer", None, mine["pc"]
        else:
            kind, prev, other = "first", None, None
        # прежние ожидающие запросы с этого ПК больше не нужны
        self.s.ex("UPDATE requests SET status='cancelled' WHERE pc=? AND status='pending'", (pc,))
        secret = secrets.token_hex(16)
        cur = self.s.ex("INSERT INTO requests(secret,kind,student_id,pc,prev_student_id,other_pc,status,created) "
                        "VALUES(?,?,?,?,?,?, 'pending', ?)", (secret, kind, sid, pc, prev, other, time.time()))
        self.s.log(sid, "login_request", {"pc": pc, "kind": kind})
        return {"status": "pending", "request_id": cur.lastrowid, "secret": secret, "kind": kind,
                "other_pc": other, "name": st["name"]}

    def request_status(self, rid: int, secret: str) -> dict:
        r = self.s.one("SELECT * FROM requests WHERE id=?", (rid,))
        if not r or not hmac.compare_digest(r["secret"], secret or ""):
            raise ApiError(404, "Запрос не найден")
        out = {"status": r["status"], "name": self.name(r["student_id"]), "student_id": r["student_id"]}
        if r["status"] == "approved":
            out["token"] = r["token"]
        return out

    def decide(self, rid: int, approve: bool) -> None:
        r = self.s.one("SELECT * FROM requests WHERE id=?", (rid,))
        if not r or r["status"] != "pending":
            return
        if not approve:
            self.s.ex("UPDATE requests SET status='denied' WHERE id=?", (rid,))
            self.s.log(r["student_id"], "login_denied", {"pc": r["pc"]})
            return
        # закрываем прежние сеансы: этого ПК и этого ученика на другом ПК
        for old in self.s.q("SELECT token, pc FROM sessions WHERE closed IS NULL AND (pc=? OR student_id=?)",
                            (r["pc"], r["student_id"])):
            reason = ("На этом компьютере вошёл другой ученик" if old["pc"] == r["pc"]
                      else f"Ты вошёл на другом компьютере ({r['pc']})")
            self.close_session(old["token"], reason)
        token = secrets.token_hex(24)
        now = time.time()
        self.s.ex("INSERT INTO sessions(token,student_id,pc,started,seen) VALUES(?,?,?,?,?)",
                  (token, r["student_id"], r["pc"], now, now))
        self.s.ex("UPDATE requests SET status='approved', token=? WHERE id=?", (token, rid))
        self.s.log(r["student_id"], "login", {"pc": r["pc"], "kind": r["kind"]})

    # ---------- ученик ----------
    def state_for(self, sess) -> dict:
        st = self.s.state()
        lesson = self.lib.lessons.get(st["lesson"], {})
        res = {}
        for r in self.s.q("SELECT task_id,status,attempts,hints,rating FROM results WHERE student_id=?",
                          (sess["student_id"],)):
            res[r["task_id"]] = {"status": r["status"], "attempts": r["attempts"], "hints": r["hints"],
                                 "rating": r["rating"]}
        help_open = self.s.one("SELECT id FROM help WHERE student_id=? AND status!='done'", (sess["student_id"],))
        return {"name": self.name(sess["student_id"]), "pc": sess["pc"], "lesson": st["lesson"],
                "title": lesson.get("title", ""), "class_id": st["class_id"], "paused": bool(st["paused"]),
                "pause_text": st["pause_text"], "timer_end": st["timer_end"], "timer_label": st["timer_label"],
                "now": time.time(), "open_tasks": st["open_tasks"], "stage": st["stage"],
                "results": res, "help_open": bool(help_open), "ai": self.ai.student_status(),
                "restart": st["restart_seq"], "close": st["close_seq"], "locked": bool(self.lock_of(sess["student_id"])),
                "play": self.play_brief(sess),
                # команды: панель заново спрашивает /api/team, только когда что-то изменилось
                "team_v": self.team_version(sess) if lesson.get("teams") else None,
                "restart_me": int((self.s.get("restart_students") or {}).get(str(sess["student_id"]), 0))}

    def lesson_for(self) -> dict:
        lesson = self.lesson()
        return {"lesson": lesson["lesson"], "title": lesson["title"], "steps": lesson["steps"],
                "theory": lesson["theory"], "stages": [],
                "training_template": training_template(lesson),
                "notebook_template": training_template(lesson),
                "files": lesson.get("_files", {}), "uses_ai": bool(lesson.get("uses_ai")), "note": lesson.get("note", ""),
                "project_idea": bool(lesson.get("project_idea")), "teams": bool(lesson.get("teams")),
                "team_task": (lesson.get("teams") or {}).get("task"),
                "tasks": [self.lib.public_task(self.lib.tasks[i], with_start=False) for i in lesson["task_ids"]],
                "cheatsheet": self.lib.cheatsheet}

    def hint(self, sess, task_id: str, level: int) -> dict:
        t = self.task(task_id)
        hints = t.get("hints", [])
        if not 1 <= level <= len(hints):
            raise ApiError(400, "Нет такой подсказки")
        sid = sess["student_id"]
        r = self.s.one("SELECT hints, attempts FROM results WHERE student_id=? AND task_id=?", (sid, task_id))
        used = r["hints"] if r else 0
        attempts = r["attempts"] if r else 0
        if level > used + 1:
            raise ApiError(400, "Сначала открой предыдущую подсказку")
        # решение пользователя: сначала ученик пробует сам; подсказка N — после N проверок
        if level > attempts:
            raise ApiError(403, "Сначала попробуй сам и нажми «Проверить». Подсказка откроется после проверки.")
        if level > used:
            self._touch_result(sid, task_id)
            self.s.ex("UPDATE results SET hints=?, updated=? WHERE student_id=? AND task_id=?",
                      (level, time.time(), sid, task_id))
            self.s.log(sid, "hint", {"task": task_id, "level": level})
        return {"level": level, "text": hints[level - 1], "total": len(hints)}

    def _touch_result(self, sid, task_id) -> None:
        self.s.ex("INSERT OR IGNORE INTO results(student_id,task_id,status,updated) VALUES(?,?,'started',?)",
                  (sid, task_id, time.time()))

    def result(self, sess, task_id: str, ok: bool, summary: str, code: str) -> dict:
        if self.lock_of(sess["student_id"]):
            raise ApiError(423, "Панель заблокирована: подожди, пока учитель разблокирует")
        t = self.task(task_id)
        sid = sess["student_id"]
        self._touch_result(sid, task_id)
        prev = self.s.one("SELECT status FROM results WHERE student_id=? AND task_id=?", (sid, task_id))
        status = "passed" if ok or prev["status"] == "passed" else "failed"
        self.s.ex("UPDATE results SET status=?, attempts=attempts+1, summary=?, code=?, updated=? "
                  "WHERE student_id=? AND task_id=?",
                  (status, (summary or "")[:300], (code or "")[:MAX_FILE], time.time(), sid, task_id))
        self.s.log(sid, "check", {"task": task_id, "ok": bool(ok)})
        out = {"status": status}
        if status == "passed":
            # решение пользователя: образец показываем сразу после того, как проверка прошла
            out["solution"] = t["_solution"]
            out["bonus"] = t.get("bonus")
        return out

    def solution(self, sess, task_id: str) -> dict:
        t = self.task(task_id)
        r = self.s.one("SELECT status FROM results WHERE student_id=? AND task_id=?", (sess["student_id"], task_id))
        if not r or r["status"] != "passed":
            raise ApiError(403, "Образец откроется, когда задание пройдёт проверку")
        return {"solution": t["_solution"], "bonus": t.get("bonus")}

    def rating(self, sess, task_id: str, rating: str) -> None:
        if rating not in ("легко", "нормально", "сложно"):
            raise ApiError(400, "Неизвестная оценка")
        self.task(task_id)
        self._touch_result(sess["student_id"], task_id)
        self.s.ex("UPDATE results SET rating=? WHERE student_id=? AND task_id=?", (rating, sess["student_id"], task_id))

    def help(self, sess, text: str, cancel: bool = False) -> dict:
        sid = sess["student_id"]
        if cancel:
            self.s.ex("UPDATE help SET status='done' WHERE student_id=? AND status!='done'", (sid,))
            return {"help_open": False}
        if not self.s.one("SELECT id FROM help WHERE student_id=? AND status!='done'", (sid,)):
            self.s.ex("INSERT INTO help(student_id,pc,text,status,created) VALUES(?,?,?, 'open', ?)",
                      (sid, sess["pc"], (text or "")[:300], time.time()))
            self.s.log(sid, "help", {"text": text})
        return {"help_open": True}

    def save_files(self, sess, files: list) -> dict:
        if not isinstance(files, list) or len(files) > MAX_FILES:
            raise ApiError(400, "Слишком много файлов")
        n = 0
        for f in files:
            path = str(f.get("path", ""))[:200]
            content = str(f.get("content", ""))
            if not path or ".." in path.split("/") or len(content.encode()) > MAX_FILE:
                continue
            self.s.ex("INSERT INTO files(student_id,path,content,updated) VALUES(?,?,?,?) "
                      "ON CONFLICT(student_id,path) DO UPDATE SET content=excluded.content, updated=excluded.updated",
                      (sess["student_id"], path, content, time.time()))
            n += 1
        return {"saved": n}

    def my_files(self, sess) -> dict:
        rows = self.s.q("SELECT path,content FROM files WHERE student_id=?", (sess["student_id"],))
        return {"files": [{"path": r["path"], "content": r["content"]} for r in rows]}

    def stage_code(self, n: int) -> dict:
        """Код тетради по этап n — только для учителя (показать на проекторе). Ученикам готовый код не выдаём."""
        lesson = self.lesson()
        if n < 1 or n > len(lesson["stages"]):
            raise ApiError(404, "Нет такого этапа")
        return {"stage": n, "code": notebook_upto(lesson["_notebook"], n)}

    # ---------- учитель ----------
    def overview(self) -> dict:
        st = self.s.state()
        if self.play_cfg()["teacher"]:
            self.play.touch(kurs_play.TEACHER, "Учитель")   # пульт открыт — учителя можно вызвать на партию
        now = time.time()
        groups = []
        for g in self.s.q("SELECT * FROM groups ORDER BY name"):
            names = [r["name"] for r in self.s.q("SELECT name FROM students WHERE group_id=? AND archived=0 ORDER BY name", (g["id"],))]
            groups.append({"id": g["id"], "name": g["name"], "students": names})
        lessons = [{"lesson": n, "title": l["title"], "steps": l["steps"], "uses_ai": bool(l.get("uses_ai")),
                    "project_idea": bool(l.get("project_idea")), "teams": bool(l.get("teams")), "tasks": [
            {"id": i, "num": self.lib.tasks[i]["num"], "title": self.lib.tasks[i]["title"],
             "level": self.lib.tasks[i]["level"], "step": self.lib.tasks[i]["step"]} for i in l["task_ids"]],
            "stages": [{"n": s["n"], "title": s["title"]} for s in l["stages"]]}
            for n, l in sorted(self.lib.lessons.items())]
        students = []
        pastes = self.guard_counts()
        if st["group_id"] is not None:
            lesson = self.lib.lessons.get(st["lesson"], {"task_ids": []})
            for r in self.s.q("SELECT * FROM students WHERE group_id=? AND archived=0 ORDER BY name", (st["group_id"],)):
                sess = self.active_session_of(r["id"])
                res = {}
                for x in self.s.q("SELECT * FROM results WHERE student_id=?", (r["id"],)):
                    if x["task_id"] in lesson["task_ids"]:
                        res[x["task_id"]] = {"status": x["status"], "attempts": x["attempts"], "hints": x["hints"],
                                             "rating": x["rating"], "summary": x["summary"]}
                students.append({"id": r["id"], "name": r["name"], "pc": sess["pc"] if sess else None,
                                 "online": bool(sess and now - sess["seen"] < ONLINE_SEC),
                                 "seen": sess["seen"] if sess else None, "results": res, "pastes": pastes.get(r["id"], 0),
                                 "locked": bool((st["locks"] or {}).get(str(r["id"])))})
        reqs = []
        for r in self.s.q("SELECT * FROM requests WHERE status='pending' ORDER BY created"):
            reqs.append({"id": r["id"], "kind": r["kind"], "name": self.name(r["student_id"]), "pc": r["pc"],
                         "prev": self.name(r["prev_student_id"]) if r["prev_student_id"] else None,
                         "other_pc": r["other_pc"], "created": r["created"]})
        helps = [{"id": h["id"], "name": self.name(h["student_id"]), "pc": h["pc"], "text": h["text"],
                  "status": h["status"], "created": h["created"]}
                 for h in self.s.q("SELECT * FROM help WHERE status!='done' ORDER BY created")]
        return {"state": st, "now": now, "groups": groups, "lessons": lessons, "students": students,
                "requests": reqs, "help": helps, "addresses": local_addresses(),
                "locks": [dict(v, student_id=int(k), name=self.name(int(k))) for k, v in (st["locks"] or {}).items()]}

    def save_group(self, name: str, names: list[str], gid=None) -> dict:
        name = (name or "").strip()[:60]
        if not name:
            raise ApiError(400, "Нужно название группы")
        names = [n.strip()[:40] for n in names if n and n.strip()]
        if gid:
            self.s.ex("UPDATE groups SET name=? WHERE id=?", (name, gid))
        else:
            try:
                gid = self.s.ex("INSERT INTO groups(name) VALUES(?)", (name,)).lastrowid
            except sqlite3.IntegrityError:
                raise ApiError(400, "Группа с таким названием уже есть") from None
        existing = {r["name"]: r["id"] for r in self.s.q("SELECT id,name FROM students WHERE group_id=?", (gid,))}
        for n in names:
            if n in existing:
                self.s.ex("UPDATE students SET archived=0 WHERE id=?", (existing[n],))
            else:
                self.s.ex("INSERT INTO students(group_id,name) VALUES(?,?)", (gid, n))
        for n, sid in existing.items():
            if n not in names:
                self.s.ex("UPDATE students SET archived=1 WHERE id=?", (sid,))
        return {"id": gid}

    def start(self, gid: int, lesson: int) -> None:
        if not self.s.one("SELECT id FROM groups WHERE id=?", (gid,)):
            raise ApiError(400, "Выбери группу")
        self.lib.load()
        if lesson not in self.lib.lessons:
            raise ApiError(400, "Нет такого занятия")
        self.s.set("running", 1)
        self.s.set("group_id", gid)
        self.s.set("lesson", lesson)
        self.s.set("open_tasks", [])
        self.s.set("paused", 0)
        self.s.set("timer_end", None)
        self.s.set("stage", 0)
        self.s.set("class_id", (self.s.get("class_id") or 0) + 1)
        self.s.log(None, "lesson_start", {"group": gid, "lesson": lesson})

    def continue_class(self) -> None:
        """Продолжить прошлое занятие: та же группа и занятие, открытые задания и этап тетради как были."""
        last = self.s.get("last_class")
        if not last:
            raise ApiError(400, "Нечего продолжать: занятие ещё не проводили")
        self.start(int(last["group_id"]), int(last["lesson"]))
        valid = set(self.lib.lessons[int(last["lesson"])]["task_ids"])
        self.s.set("open_tasks", [t for t in last.get("open_tasks") or [] if t in valid])
        self.s.set("stage", int(last.get("stage") or 0))

    # ---------- игры по сети класса: доступ открывает учитель, время не тратится ----------
    PLAY_MODES = ("off", "all", "done")   # закрыты · всем · тем, кто решил все открытые задания

    def play_cfg(self) -> dict:
        cfg = dict(DEFAULT_STATE["play"])
        cfg.update(self.s.get("play") or {})
        return cfg

    def play_allowed(self, sid) -> tuple[bool, str]:
        st = self.s.state()
        cfg = self.play_cfg()
        if not st["running"]:
            return False, "Занятие не идёт"
        if st["paused"]:
            return False, "Пауза: смотрим на учителя"
        if self.lock_of(sid):
            return False, "Панель заблокирована"
        if sid in cfg["allow"] or cfg["mode"] == "all":
            return True, ""
        if cfg["mode"] == "done":
            open_ids = st["open_tasks"] or []
            passed = {r["task_id"] for r in self.s.q("SELECT task_id FROM results WHERE student_id=? AND status='passed'", (sid,))}
            if open_ids and all(t in passed for t in open_ids):
                return True, ""
            return False, "Игры откроются, когда решишь все открытые задания"
        return False, "Игры закрыты — их открывает учитель"

    def play_candidates(self) -> dict:
        """Кого сейчас можно вызвать: ключ → имя (ученики группы с доступом и учитель, если принимает вызовы)."""
        out = {}
        gid = self.s.get("group_id")
        for r in self.s.q("SELECT id, name FROM students WHERE group_id=? AND archived=0", (gid,)):
            if self.play_allowed(r["id"])[0]:
                out[f"s:{r['id']}"] = r["name"]
        if self.play_cfg()["teacher"]:
            out[kurs_play.TEACHER] = "Учитель"
        return out

    def play_brief(self, sess) -> dict:
        """Для панели ученика: можно ли играть, кто зовёт и идёт ли партия (видно на любой вкладке)."""
        sid = sess["student_id"]
        key = f"s:{sid}"
        ok, why = self.play_allowed(sid)
        if not ok:
            self.play.forget(key)
            if self.play.match_of(key):
                self.play.leave(key, why)
            return {"allowed": False, "reason": why, "games": [], "invite": None, "match": None}
        self.play.touch(key, self.name(sid))
        info = self.play.info(key)
        return {"allowed": True, "reason": "", "games": self.play_cfg()["games"],
                "invite": info["invites_in"][0] if info["invites_in"] else None,
                "match": info["match"]}

    def play_lobby(self, key: str, name: str) -> dict:
        allowed = self.play_candidates()
        online = self.play.online()
        busy = self.play.busy()
        players = [{"key": k, "name": n, "busy": k in busy} for k, n in allowed.items()
                   if k in online and k != key]
        players.sort(key=lambda p: (p["key"] != kurs_play.TEACHER, p["name"]))
        return dict(self.play.info(key), players=players, games=self.play_cfg()["games"],
                    titles=kurs_play.GAMES, me={"key": key, "name": name})

    def play_action(self, key: str, name: str, action: str, b: dict) -> dict:
        try:
            if action == "invite":
                game = str(b.get("game", ""))
                if game not in self.play_cfg()["games"]:
                    raise kurs_play.PlayError("Эта игра сейчас закрыта")
                return {"id": self.play.invite(key, name, str(b.get("to", "")), game, self.play_candidates())}
            if action == "answer":
                m = self.play.answer(str(b.get("id", "")), key, bool(b.get("accept")))
                if m:
                    self.s.log(None, "play_start", {"game": m["game"], "names": m["names"]})
                return {"match": self.play.public_match(m, key) if m else None}
            if action == "cancel":
                self.play.cancel(str(b.get("id", "")), key)
                return {"ok": True}
            if action == "leave":
                self.play.leave(key, f"{name} вышел из партии")
                return {"ok": True}
        except kurs_play.PlayError as e:
            raise ApiError(409, str(e)) from None
        raise ApiError(404, "Нет такой команды")

    def play_teacher(self) -> dict:
        if self.play_cfg()["teacher"]:
            self.play.touch(kurs_play.TEACHER, "Учитель")
        else:
            self.play.forget(kurs_play.TEACHER)
        out = self.play_lobby(kurs_play.TEACHER, "Учитель")
        out["config"] = self.play_cfg()
        out["matches"] = self.play.list_matches()
        online = self.play.online()
        gid = self.s.get("group_id")
        out["students"] = [{"id": r["id"], "name": r["name"], "allowed": self.play_allowed(r["id"])[0],
                            "manual": r["id"] in self.play_cfg()["allow"], "online": f"s:{r['id']}" in online}
                           for r in self.s.q("SELECT id, name FROM students WHERE group_id=? AND archived=0 ORDER BY name", (gid,))]
        return out

    def play_config(self, b: dict) -> None:
        cfg = self.play_cfg()
        if "mode" in b:
            if b["mode"] not in self.PLAY_MODES:
                raise ApiError(400, "Неизвестный режим")
            cfg["mode"] = b["mode"]
        if "games" in b:
            cfg["games"] = [g for g in b["games"] if g in kurs_play.GAMES]
        if "teacher" in b:
            cfg["teacher"] = bool(b["teacher"])
        if "allow" in b:
            sid, on = int(b["allow"].get("student_id") or 0), bool(b["allow"].get("on"))
            allow = [x for x in cfg["allow"] if x != sid]
            cfg["allow"] = allow + ([sid] if on else [])
        self.s.set("play", cfg)
        if cfg["mode"] == "off" and not cfg["allow"]:
            self.play.stop_all("Учитель закрыл игры")

    # ---------- проект: идеи учеников и команды ----------
    def idea_of(self, sid) -> dict | None:
        r = self.s.one("SELECT * FROM ideas WHERE student_id=?", (sid,))
        return {"title": r["title"], "about": r["about"], "tools": r["tools"], "updated": r["updated"]} if r else None

    def idea_save(self, sess, b: dict) -> dict:
        vals = {k: str(b.get(k) or "").strip()[:n] for k, n in IDEA_LIMITS.items()}
        if not any(vals.values()):
            raise ApiError(400, "Напиши хотя бы название идеи")
        self.s.ex("INSERT INTO ideas(student_id,title,about,tools,updated) VALUES(?,?,?,?,?) ON CONFLICT(student_id) "
                  "DO UPDATE SET title=excluded.title, about=excluded.about, tools=excluded.tools, updated=excluded.updated",
                  (sess["student_id"], vals["title"], vals["about"], vals["tools"], time.time()))
        self.s.log(sess["student_id"], "idea", vals)
        return {"idea": self.idea_of(sess["student_id"])}

    def teams_cfg(self) -> dict:
        cfg = dict(DEFAULT_STATE["teams"])
        cfg.update(self.s.get("teams") or {})
        return cfg

    def team_task(self) -> dict | None:
        """Задание «Мои инструменты», если идёт занятие с командами: из его файла товарищи получают инструменты."""
        lesson = self.lib.lessons.get(self.s.get("lesson"), {})
        return self.lib.tasks.get((lesson.get("teams") or {}).get("task", ""))

    def team_rows(self, gid=None):
        return self.s.q("SELECT * FROM teams WHERE group_id=? ORDER BY id", (self.s.get("group_id") if gid is None else gid,))

    def team_row(self, tid):
        r = self.s.one("SELECT * FROM teams WHERE id=?", (tid,))
        if not r or r["group_id"] != self.s.get("group_id"):
            raise ApiError(404, "Нет такой команды")
        return r

    def team_of(self, sid):
        return self.s.one("SELECT t.* FROM teams t JOIN team_members m ON m.team_id=t.id WHERE m.student_id=?", (sid,))

    def team_members(self, tid):
        return self.s.q("SELECT s.id, s.name, m.plan, m.joined FROM team_members m JOIN students s ON s.id=m.student_id "
                        "WHERE m.team_id=? AND s.archived=0 ORDER BY m.joined", (tid,))

    def team_notice(self, sid, text: str | None) -> None:
        notices = dict(self.s.get("team_notices") or {})
        if text:
            notices[str(sid)] = text
        else:
            notices.pop(str(sid), None)
        self.s.set("team_notices", notices)

    @staticmethod
    def tool_names(code: str) -> list[str]:
        """Имена инструментов из файла ученика: make_tool("имя", ...). Нужны, чтобы заметить одинаковые имена в команде."""
        return [n for n in re.findall(r"make_tool\(\s*[\"']([^\"']+)[\"']", code or "") if "___" not in n]

    def team_file(self, sid) -> tuple[str, float] | None:
        """Файл «Мои инструменты» ученика: (текст, когда сохранён)."""
        t = self.team_task()
        if not t:
            return None
        r = self.s.one("SELECT content, updated FROM files WHERE student_id=? AND path=?",
                       (sid, f"Занятие_{t['lesson']}/{t['file']}"))
        return (r["content"], r["updated"]) if r else None

    def _online(self, sid, now: float) -> bool:
        sess = self.active_session_of(sid)
        return bool(sess and now - sess["seen"] < ONLINE_SEC)

    def _task_status(self, sid) -> str | None:
        t = self.team_task()
        r = self.s.one("SELECT status FROM results WHERE student_id=? AND task_id=?", (sid, t["id"])) if t else None
        return r["status"] if r else None

    def team_view(self, sess) -> dict:
        """Всё про команды для панели ученика: список команд, своя команда, файлы товарищей."""
        sid = sess["student_id"]
        cfg = self.teams_cfg()
        now = time.time()
        mine = self.team_of(sid)
        teams = []
        for t in self.team_rows():
            names = [m["name"] for m in self.team_members(t["id"])]
            teams.append({"id": t["id"], "name": t["name"], "topic": t["topic"], "bot_name": t["bot_name"],
                          "members": names, "full": bool(cfg["max"]) and len(names) >= cfg["max"],
                          "banned": sid in json.loads(t["banned"] or "[]")})
        out = {"cfg": cfg, "teams": teams, "my": mine["id"] if mine else None, "team": None,
               "notice": (self.s.get("team_notices") or {}).get(str(sid), "")}
        if mine:
            members, files, used = [], [], set()
            for m in self.team_members(mine["id"]):
                f = self.team_file(m["id"])
                base = re.sub(r"[^\w\-]+", "_", m["name"]).strip("_") or f"ученик_{m['id']}"
                if base in used:
                    base = f"{base}_{m['id']}"
                used.add(base)
                members.append({"id": m["id"], "name": m["name"], "me": m["id"] == sid, "plan": m["plan"],
                                "online": self._online(m["id"], now), "idea": self.idea_of(m["id"]),
                                "status": self._task_status(m["id"]), "tools": self.tool_names(f[0]) if f else [],
                                "file": base + ".py"})
                if f and m["id"] != sid:
                    files.append({"student_id": m["id"], "author": m["name"], "name": base + ".py", "content": f[0]})
            out["team"] = {"id": mine["id"], "name": mine["name"], "topic": mine["topic"], "bot_name": mine["bot_name"],
                           "persona": mine["persona"], "edited_by": mine["edited_by"], "members": members, "files": files}
        return out

    def team_version(self, sess) -> str:
        return hashlib.sha1(json.dumps(self.team_view(sess), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    def _need_team_lesson(self) -> None:
        if not self.team_task():
            raise ApiError(409, "Команды собираются на занятии-проекте")

    def team_join(self, sess, tid: int) -> None:
        self._need_team_lesson()
        sid = sess["student_id"]
        cfg = self.teams_cfg()
        if not cfg["open"]:
            raise ApiError(403, "Запись в команды закрыта — попроси учителя")
        t = self.team_row(tid)
        if sid in json.loads(t["banned"] or "[]"):
            raise ApiError(403, "Учитель убрал тебя из этой команды — выбери другую")
        cur = self.team_of(sid)
        if cur and cur["id"] == tid:
            return
        if cfg["max"] and len(self.team_members(tid)) >= cfg["max"]:
            raise ApiError(409, f"В команде уже {cfg['max']} — выбери другую")
        self.s.ex("INSERT INTO team_members(student_id,team_id,joined) VALUES(?,?,?) ON CONFLICT(student_id) "
                  "DO UPDATE SET team_id=excluded.team_id, plan='', joined=excluded.joined", (sid, tid, time.time()))
        self.team_notice(sid, None)
        self.s.log(sid, "team_join", {"team": t["name"]})

    def team_leave(self, sess) -> None:
        if not self.teams_cfg()["open"]:
            raise ApiError(403, "Запись в команды закрыта — попроси учителя")
        t = self.team_of(sess["student_id"])
        if t:
            self.s.ex("DELETE FROM team_members WHERE student_id=?", (sess["student_id"],))
            self.s.log(sess["student_id"], "team_leave", {"team": t["name"]})

    def team_card(self, sess, b: dict) -> None:
        t = self.team_of(sess["student_id"])
        if not t:
            raise ApiError(409, "Сначала вступи в команду")
        for k, n in TEAM_LIMITS.items():
            if k in b:
                self.s.ex(f"UPDATE teams SET {k}=? WHERE id=?", (str(b[k] or "").strip()[:n], t["id"]))
        self.s.ex("UPDATE teams SET edited_by=?, updated=? WHERE id=?", (self.name(sess["student_id"]), time.time(), t["id"]))

    def team_plan(self, sess, plan: str) -> None:
        if not self.team_of(sess["student_id"]):
            raise ApiError(409, "Сначала вступи в команду")
        self.s.ex("UPDATE team_members SET plan=? WHERE student_id=?", (str(plan or "").strip()[:200], sess["student_id"]))

    def teams_teacher(self) -> dict:
        """Пульт: команды группы, кто без команды и идеи учеников."""
        gid = self.s.get("group_id")
        cfg = self.teams_cfg()
        now = time.time()
        students = self.s.q("SELECT id, name FROM students WHERE group_id=? AND archived=0 ORDER BY name", (gid,)) if gid else []
        in_team = set()
        teams = []
        team_name = {}
        for t in self.team_rows() if gid else []:
            members = []
            for m in self.team_members(t["id"]):
                in_team.add(m["id"])
                f = self.team_file(m["id"])
                members.append({"id": m["id"], "name": m["name"], "plan": m["plan"], "online": self._online(m["id"], now),
                                "status": self._task_status(m["id"]), "tools": self.tool_names(f[0]) if f else []})
                team_name[m["id"]] = t["name"]
            banned = json.loads(t["banned"] or "[]")
            teams.append({"id": t["id"], "name": t["name"], "topic": t["topic"], "bot_name": t["bot_name"],
                          "persona": t["persona"], "edited_by": t["edited_by"], "members": members,
                          "banned": [{"id": b, "name": self.name(b)} for b in banned]})
        free = [{"id": r["id"], "name": r["name"], "online": self._online(r["id"], now)} for r in students if r["id"] not in in_team]
        ideas = []
        for r in students:
            idea = self.idea_of(r["id"])
            if idea:
                ideas.append(dict(idea, student_id=r["id"], name=r["name"], team=team_name.get(r["id"])))
        return {"cfg": cfg, "teams": teams, "free": free, "ideas": ideas, "team_lesson": bool(self.team_task()),
                "group": bool(gid)}

    def teams_create(self, count: int, names: list) -> None:
        gid = self.s.get("group_id")
        if not gid:
            raise ApiError(400, "Сначала начните занятие с группой")
        have = self.team_rows()
        count = max(0, min(int(count or 0), MAX_TEAMS - len(have)))
        if not count:
            raise ApiError(400, f"Команд уже {len(have)} — больше {MAX_TEAMS} нельзя" if have else "Сколько команд создать?")
        taken = {t["name"] for t in have}
        now = time.time()
        for i in range(count):
            name = (str(names[i]).strip()[:40] if i < len(names or []) and str(names[i]).strip() else "")
            n = len(have) + i + 1          # «Команда N» — по месту в списке
            while not name or name in taken:
                name = f"Команда {n}"
                n += 1
            taken.add(name)
            self.s.ex("INSERT INTO teams(group_id,name,created,updated) VALUES(?,?,?,?)", (gid, name, now, now))
        self.s.log(None, "teams_create", {"count": count})

    def teams_config(self, b: dict) -> None:
        cfg = self.teams_cfg()
        if "open" in b:
            cfg["open"] = bool(b["open"])
        for k in ("min", "max"):
            if k in b:
                cfg[k] = max(0, min(int(b[k] or 0), 50))
        self.s.set("teams", cfg)

    def teams_delete(self, tid: int | None) -> None:
        ids = [self.team_row(tid)["id"]] if tid else [t["id"] for t in self.team_rows()]
        for i in ids:
            self.s.ex("DELETE FROM team_members WHERE team_id=?", (i,))
            self.s.ex("DELETE FROM teams WHERE id=?", (i,))

    def teams_kick(self, sid: int) -> None:
        """Учитель убирает ученика из команды: вернуться в неё сам он уже не сможет (перевести может учитель)."""
        t = self.team_of(sid)
        if not t:
            return
        banned = json.loads(t["banned"] or "[]")
        if sid not in banned:
            banned.append(sid)
        self.s.ex("UPDATE teams SET banned=? WHERE id=?", (json.dumps(banned), t["id"]))
        self.s.ex("DELETE FROM team_members WHERE student_id=?", (sid,))
        self.team_notice(sid, f"Учитель убрал тебя из команды «{t['name']}». Выбери другую команду.")
        self.s.log(sid, "team_kick", {"team": t["name"]})

    def teams_assign(self, sid: int, tid: int) -> None:
        """Учитель сам переводит ученика в команду (или выводит из команды, если tid = 0): без ограничений записи."""
        st = self.student(sid)
        if not st or st["group_id"] != self.s.get("group_id"):
            raise ApiError(404, "Нет такого ученика")
        if not tid:
            t = self.team_of(sid)
            self.s.ex("DELETE FROM team_members WHERE student_id=?", (sid,))
            if t:
                self.team_notice(sid, f"Учитель вывел тебя из команды «{t['name']}».")
            return
        t = self.team_row(tid)
        banned = [x for x in json.loads(t["banned"] or "[]") if x != sid]
        self.s.ex("UPDATE teams SET banned=? WHERE id=?", (json.dumps(banned), tid))
        cur = self.team_of(sid)
        if cur and cur["id"] == tid:
            return
        self.s.ex("INSERT INTO team_members(student_id,team_id,joined) VALUES(?,?,?) ON CONFLICT(student_id) "
                  "DO UPDATE SET team_id=excluded.team_id, plan='', joined=excluded.joined", (sid, tid, time.time()))
        self.team_notice(sid, f"Учитель перевёл тебя в команду «{t['name']}».")
        self.s.log(sid, "team_assign", {"team": t["name"]})

    def teams_rename(self, tid: int, name: str) -> None:
        name = (name or "").strip()[:40]
        if not name:
            raise ApiError(400, "Нужно название команды")
        self.team_row(tid)
        self.s.ex("UPDATE teams SET name=?, updated=? WHERE id=?", (name, time.time(), tid))

    def end(self) -> None:
        self.play.stop_all("Занятие завершено")
        # запоминаем, где остановились: «Продолжить занятие» вернёт открытые задания и этап
        if self.s.get("running"):
            self.s.set("last_class", {k: self.s.get(k) for k in ("group_id", "lesson", "open_tasks", "stage")})
            try:
                self.export_projects_data()
            except Exception as e:
                print("Auto-export projects error:", e)
        for r in self.s.q("SELECT token FROM sessions WHERE closed IS NULL"):
            self.close_session(r["token"], "Занятие завершено")
        self.s.ex("UPDATE requests SET status='cancelled' WHERE status='pending'")
        self.s.ex("UPDATE help SET status='done' WHERE status!='done'")
        self.s.set("running", 0)
        self.s.set("paused", 0)
        self.s.set("timer_end", None)
        self.s.log(None, "lesson_end")

    def open_tasks(self, ids: list[str], is_open: bool) -> None:
        cur = list(self.s.get("open_tasks") or [])
        lesson = self.lesson()
        for i in ids:
            if i not in lesson["task_ids"]:
                continue
            if is_open and i not in cur:
                cur.append(i)
            if not is_open and i in cur:
                cur.remove(i)
        cur.sort(key=lambda i: self.lib.tasks[i]["num"])
        self.s.set("open_tasks", cur)

    GUARD_EVENTS = ("paste_blocked", "ai_paste_blocked", "outside_edit")

    def student_event(self, sess, body: dict) -> dict:
        """Панель сообщает: ученик пытался вставить готовый код или менял файл в обход редактора."""
        kind = str(body.get("kind", ""))
        if kind not in self.GUARD_EVENTS:
            raise ApiError(400, "Неизвестное событие")
        text = str(body.get("text", ""))

        is_ai = False
        verdict_reason = ""
        if kind == "ai_paste_blocked":
            is_ai = True
            verdict_reason = "явные признаки кода нейросети"
        elif kind == "paste_blocked" and len(text.strip()) >= 20:
            is_ai, verdict_reason = self.ai.check_ai_code(text)
            if is_ai:
                kind = "ai_paste_blocked"

        data = {"pc": sess["pc"], "file": str(body.get("file", ""))[:80],
                "chars": int(body.get("chars") or 0), "text": text[:400],
                "reason": verdict_reason}
        self.s.log(sess["student_id"], kind, data)
        # Блокировка ТОЛЬКО если ИИ подтвердил вставку кода или правку вне редактора!
        if self.s.get("lock_on_paste") and kind in ("ai_paste_blocked", "outside_edit"):
            locks = dict(self.s.get("locks") or {})
            key = str(sess["student_id"])
            if key not in locks:
                locks[key] = dict(data, kind=kind, ts=time.time())
                self.s.set("locks", locks)
            return {"ok": True, "locked": True, "is_ai": is_ai, "reason": verdict_reason}
        return {"ok": True, "locked": False, "is_ai": is_ai, "reason": verdict_reason}

    def lock_of(self, sid):
        return (self.s.get("locks") or {}).get(str(sid))

    def unlock(self, sid: int) -> None:
        locks = dict(self.s.get("locks") or {})
        if locks.pop(str(sid), None) is not None:
            self.s.set("locks", locks)
            self.s.log(sid, "unlock")

    def lesson_started_at(self) -> float:
        r = self.s.one("SELECT MAX(ts) AS ts FROM events WHERE kind='lesson_start'")
        return (r["ts"] if r else None) or 0

    def guard_counts(self) -> dict:
        since = self.lesson_started_at()
        placeholders = ",".join("?" for _ in self.GUARD_EVENTS)
        rows = self.s.q(f"SELECT student_id, COUNT(*) AS n FROM events WHERE kind IN ({placeholders}) AND ts>=? GROUP BY student_id",
                        (*self.GUARD_EVENTS, since))
        return {r["student_id"]: r["n"] for r in rows}

    def student_detail(self, sid: int) -> dict:
        r = self.student(sid)
        if not r:
            raise ApiError(404, "Нет такого ученика")
        res = [dict(x) for x in self.s.q("SELECT * FROM results WHERE student_id=? ORDER BY task_id", (sid,))]
        files = [dict(x) for x in self.s.q("SELECT path,content,updated FROM files WHERE student_id=? ORDER BY path", (sid,))]
        placeholders = ",".join("?" for _ in self.GUARD_EVENTS)
        pastes = [dict(json.loads(x["data"] or "{}"), ts=x["ts"], kind=x["kind"]) for x in self.s.q(
            f"SELECT * FROM events WHERE student_id=? AND kind IN ({placeholders}) ORDER BY ts DESC LIMIT 20", (sid, *self.GUARD_EVENTS))]
        ai_queries = [dict(id=x["id"], ts=x["ts"], pc=x["pc"], question=x["question"],
                           system=x["system"], answer=x["answer"], status=x["status"],
                           ms=x["ms"], cached=bool(x["cached"]),
                           flags=[f for f in (x["flags"] or "").split(",") if f])
                      for x in self.s.q("SELECT * FROM ai_log WHERE student_id=? ORDER BY id DESC LIMIT 50", (sid,))]
        return {"id": sid, "name": r["name"], "results": res, "files": files, "pastes": pastes, "ai_queries": ai_queries}

    def export_csv(self) -> str:
        st = self.s.state()
        lesson = self.lib.lessons.get(st["lesson"], {"task_ids": []})
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Ученик"] + [f"{self.lib.tasks[i]['num']}. {self.lib.tasks[i]['title']}" for i in lesson["task_ids"]])
        for s in self.overview()["students"]:
            row = [s["name"]]
            for i in lesson["task_ids"]:
                r = s["results"].get(i)
                if not r:
                    row.append("")
                else:
                    mark = {"passed": "выполнено", "failed": "не выполнено", "started": "начато"}[r["status"]]
                    row.append(f"{mark}; попыток {r['attempts']}; подсказок {r['hints']}")
            w.writerow(row)
        return "﻿" + buf.getvalue()

    def export_projects_data(self) -> dict:
        """Полная структурированная выгрузка проектов команд и идей в JSON для анализа и парсинга."""
        gid = self.s.get("group_id")
        group_row = self.s.one("SELECT name FROM groups WHERE id=?", (gid,)) if gid else None
        group_name = group_row["name"] if group_row else "Общая группа"
        st = self.s.state()
        now = time.time()

        teams_list = []
        for t in self.team_rows() if gid else []:
            members = []
            for m in self.team_members(t["id"]):
                f = self.team_file(m["id"])
                if not f:
                    r = self.s.one(
                        "SELECT content, updated FROM files WHERE student_id=? AND path LIKE '%Мои_инструменты.py' ORDER BY updated DESC LIMIT 1",
                        (m["id"],)
                    )
                    if r:
                        f = (r["content"], r["updated"])
                code_content = f[0] if f else ""
                student_files = [
                    {"path": r["path"], "content": r["content"], "updated": r["updated"]}
                    for r in self.s.q("SELECT path, content, updated FROM files WHERE student_id=?", (m["id"],))
                ]
                members.append({
                    "student_id": m["id"],
                    "name": m["name"],
                    "plan": m["plan"],
                    "status": self._task_status(m["id"]),
                    "tools": self.tool_names(code_content) if code_content else [],
                    "code": code_content,
                    "updated": f[1] if f else None,
                    "files": student_files,
                })
            banned = json.loads(t["banned"] or "[]")
            teams_list.append({
                "team_id": t["id"],
                "team_name": t["name"],
                "topic": t["topic"],
                "bot_name": t["bot_name"],
                "persona": t["persona"],
                "edited_by": t["edited_by"],
                "created": t["created"],
                "updated": t["updated"],
                "members": members,
                "banned": [{"id": b, "name": self.name(b)} for b in banned],
            })

        ideas_list = []
        students = self.s.q("SELECT id, name FROM students WHERE group_id=? AND archived=0 ORDER BY name", (gid,)) if gid else []
        for s in students:
            idea = self.idea_of(s["id"])
            if idea:
                ideas_list.append({
                    "student_id": s["id"],
                    "name": s["name"],
                    "title": idea.get("title", ""),
                    "about": idea.get("about", ""),
                    "tools": idea.get("tools", ""),
                    "updated": idea.get("updated"),
                })

        out = {
            "version": "1.0",
            "exported_at": now,
            "exported_at_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "group": group_name,
            "group_id": gid,
            "lesson": st.get("lesson", 6),
            "teams_count": len(teams_list),
            "teams": teams_list,
            "ideas": ideas_list,
        }

        # Автоматическое резервное сохранение на диск учительского ПК
        try:
            proj_dir = os.path.join(self.s.data_dir, "projects")
            os.makedirs(proj_dir, exist_ok=True)
            safe_grp = re.sub(r"[^\w\-]", "_", group_name)
            save_path = os.path.join(proj_dir, f"projects_{safe_grp}.json")
            with open(save_path, "w", encoding="utf-8") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Auto-save projects json error:", e)

        return out

    def export_projects_zip(self) -> bytes:
        """Собирает ZIP-архив со всеми проектами: JSON, папки команд, файлы участников и Наш_бот.py."""
        data = self.export_projects_data()
        group_name = data.get("group", "class")
        safe_grp = re.sub(r"[^\w\-]", "_", group_name)

        code_dir = os.path.join(REPO, "Код")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            # 1. Главный машиночитаемый JSON
            z.writestr("projects.json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

            # 2. Идеи отдельным файлом
            z.writestr("ideas.json", json.dumps(data.get("ideas", []), ensure_ascii=False, indent=2).encode("utf-8"))

            # 3. Для каждой команды — готовая к запуску папка
            for team in data.get("teams", []):
                t_name = re.sub(r"[^\w\-]", "_", team.get("team_name") or f"Команда_{team['team_id']}")
                b_name = re.sub(r"[^\w\-]", "_", team.get("bot_name") or "Бот")
                folder = f"{t_name}_{b_name}"

                # команда.json
                card = {
                    "team": team.get("team_name"),
                    "bot_name": team.get("bot_name"),
                    "topic": team.get("topic"),
                    "persona": team.get("persona"),
                    "members": [m["name"] for m in team.get("members", [])],
                }
                z.writestr(f"{folder}/команда.json", json.dumps(card, ensure_ascii=False, indent=2).encode("utf-8"))

                # Вспомогательные модули для автономного запуска бота
                for mod in ("ai.py", "agent.py", "Наш_бот.py"):
                    mod_path = os.path.join(code_dir, mod)
                    if os.path.isfile(mod_path):
                        with open(mod_path, "rb") as fh:
                            z.writestr(f"{folder}/{mod}", fh.read())

                # Файлы участников
                for m in team.get("members", []):
                    m_name = re.sub(r"[^\w\-]", "_", m["name"])
                    code = m.get("code") or "# Ученик пока не сохранил файл\n"
                    z.writestr(f"{folder}/{m_name}_Мои_инструменты.py", code.encode("utf-8"))
                    z.writestr(f"{folder}/Команда/{m_name}.py", code.encode("utf-8"))

                    # Дополнительные файлы ученика (например память_бота.json)
                    for sf in m.get("files", []):
                        fname = os.path.basename(sf.get("path", ""))
                        if fname and fname not in ("Мои_инструменты.py", f"{m_name}.py"):
                            z.writestr(f"{folder}/{fname}", (sf.get("content") or "").encode("utf-8"))

        zip_bytes = buf.getvalue()

        # Сохраняем копию архива на диск учительского ПК
        try:
            proj_dir = os.path.join(self.s.data_dir, "projects")
            os.makedirs(proj_dir, exist_ok=True)
            zip_save_path = os.path.join(proj_dir, f"projects_{safe_grp}.zip")
            with open(zip_save_path, "wb") as fh:
                fh.write(zip_bytes)
        except Exception as e:
            print("Auto-save projects zip error:", e)

        return zip_bytes


def _day_start() -> float:
    """Начало сегодняшнего дня по местному времени."""
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def local_addresses() -> list[str]:
    """Адреса этого компьютера. Первым — адрес основной сети (через него идёт маршрут по умолчанию):
    его пульт подставляет в команду подключения. Docker и прочие виртуальные сети — в конце."""
    main = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        main = s.getsockname()[0]
        s.close()
    except OSError:
        pass
    out = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            out.add(info[4][0])
    except OSError:
        pass
    rest = sorted((a for a in out if not a.startswith("127.") and a != main), key=lambda a: (a.startswith("172.17."), a))
    return ([main] if main and not main.startswith("127.") else []) + rest


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
                ".py": "text/x-python; charset=utf-8", ".vsix": "application/octet-stream",
                ".svg": "image/svg+xml", ".png": "image/png"}


def content_disposition(filename: str) -> str:
    """Формирует безопасный заголовок Content-Disposition по стандарту RFC 5987 / RFC 6266.

    ASCII fallback для старых клиентов и UTF-8 кодирование для современных браузеров.
    Предотвращает UnicodeEncodeError в http.server при наличии кириллицы в названии файла.
    """
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    ascii_fallback = f"projects.{ext}" if ext else "download.bin"
    utf8_quoted = quote(filename, encoding="utf-8")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'


class Handler(BaseHTTPRequestHandler):
    server_version = "KursServer/" + VERSION
    kurs: Kurs = None  # type: ignore[assignment]
    web_dir = os.path.join(HERE, "web")
    client_dir = os.path.join(KURS, "client", "dist")
    media_dir = os.path.join(KURS, "vscode", "media")
    quiet = False

    def log_message(self, fmt, *args):  # noqa: D401
        if not self.quiet:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # --- ответы ---
    def send_json(self, data, status: int = 200, headers: dict | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, ctype: str, status: int = 200, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            val = str(v)
            try:
                val.encode("latin-1")
                self.send_header(k, val)
            except UnicodeEncodeError:
                self.send_header(k, quote(val, safe=";= \"'*-"))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, folder: str, name: str) -> None:
        path = os.path.realpath(os.path.join(folder, name))
        if not path.startswith(os.path.realpath(folder) + os.sep) or not os.path.isfile(path):
            return self.send_json({"error": "Не найдено"}, 404)
        with open(path, "rb") as fh:
            body = fh.read()
        headers = {}
        if folder in (self.web_dir, self.media_dir):
            host = re.sub(r"[^A-Za-z0-9.:\-\[\]]", "", self.headers.get("Host") or "")
            headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                  f"img-src 'self' data:; connect-src 'self' ws://{host}; frame-ancestors 'none'")
        self.send_bytes(body, STATIC_TYPES.get(os.path.splitext(path)[1], "application/octet-stream"), 200, headers)

    # --- разбор запроса ---
    def body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ApiError(413, "Слишком большой запрос")
        if n == 0:
            return {}
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ApiError(415, "Нужен JSON")
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Неверный JSON") from None
        if not isinstance(data, dict):
            raise ApiError(400, "Неверный JSON")
        return data

    def is_local(self) -> bool:
        return self.client_address[0] in LOCAL

    def teacher_ok(self) -> bool:
        if not self.is_local():
            return False
        c = cookies.SimpleCookie(self.headers.get("Cookie") or "")
        tok = c.get("kurs_teacher")
        if not tok:
            return False
        exp = self.kurs.s.teacher_tokens.get(tok.value)
        return bool(exp and exp > time.time())

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method: str) -> None:
        u = urlparse(self.path)
        path = u.path
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if path == "/ws/play" and method == "GET":
                return self.ws_play(qs)
            if path == "/tapi/ai/test" and method == "POST":
                if not self.teacher_ok():
                    raise ApiError(401, "Нужно войти")
                return self.send_json(self.kurs.ai.test())
            with self.kurs.s.lock:
                if path.startswith("/api/"):
                    return self.student_api(method, path[5:], qs)
                if path.startswith("/tapi/"):
                    return self.teacher_api(method, path[6:], qs)
                self.kurs.s.db.commit()
            if path in ("/", "/teacher", "/teacher/"):
                if not self.is_local():
                    return self.send_bytes("Страница учителя открывается только на учительском компьютере.".encode(),
                                           "text/plain; charset=utf-8", 403)
                return self.send_static(self.web_dir, "teacher.html")
            if path.startswith("/teacher/"):
                if not self.is_local():
                    return self.send_json({"error": "Только на учительском компьютере"}, 403)
                if path == "/teacher/play.js":       # игры — тот же файл, что и в панели ученика
                    return self.send_static(self.media_dir, "play.js")
                return self.send_static(self.web_dir, path[len("/teacher/"):])
            if path.startswith("/client/"):
                return self.send_static(self.client_dir, path[len("/client/"):])
            if path in ("/k", "/k/"):
                # короткая команда для ПК ученика: wget -qO- http://IP:8000/k | python3 - --shortcut
                # отдаём запуск курса с уже вписанным адресом этого сервера
                host = re.sub(r"[^A-Za-z0-9.:\-\[\]]", "", self.headers.get("Host") or "")
                try:
                    with open(os.path.join(self.client_dir, "kurs_start.py"), encoding="utf-8") as fh:
                        src = fh.read()
                except OSError:
                    return self.send_json({"error": "Не найдено"}, 404)
                src = src.replace('DEFAULT_SERVER = ""', f'DEFAULT_SERVER = "http://{host}"', 1)
                return self.send_bytes(src.encode("utf-8"), "text/x-python; charset=utf-8")
            return self.send_json({"error": "Не найдено"}, 404)
        except ApiError as e:
            self.kurs.s.db.rollback()
            return self.send_json(dict(e.extra, error=e.message), e.status)
        except Exception as e:  # noqa: BLE001
            self.kurs.s.db.rollback()
            sys.stderr.write(f"Ошибка сервера: {e!r}\n")
            return self.send_json({"error": "Ошибка сервера"}, 500)

    # --- партия по WebSocket ---
    def ws_play(self, qs: dict) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or (self.headers.get("Upgrade") or "").lower() != "websocket":
            raise ApiError(400, "Нужен WebSocket")
        teacher = self.teacher_ok()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", kurs_play.ws_accept(key))
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        self.connection.settimeout(90)          # клиент шлёт ping каждые 15 с; пропал — отключаем
        try:
            op, payload = kurs_play.ws_read(self.rfile)     # первое сообщение — {"auth": ключ сеанса ученика}
            token = json.loads(payload.decode("utf-8")).get("auth") if op == 1 else None
            if teacher:
                pkey = kurs_play.TEACHER
            else:
                with self.kurs.s.lock:
                    sess = self.kurs.live_session(token)
                    self.kurs.s.db.commit()
                pkey = f"s:{sess['student_id']}"
        except (ApiError, OSError, ValueError, AttributeError):
            try:
                kurs_play.ws_send(self.wfile, json.dumps({"type": "stopped", "reason": "Не удалось войти в партию"}, ensure_ascii=False))
            except OSError:
                pass
            return
        self.kurs.play.serve(qs.get("match", ""), pkey, self.wfile, self.rfile)

    # --- API ученика ---
    def student_api(self, method: str, name: str, qs: dict) -> None:
        k = self.kurs
        token = self.headers.get("X-Kurs-Token")
        auth = self.headers.get("Authorization") or ""
        if not token and auth.startswith("Bearer "):
            token = auth[7:].strip()      # так ключ передаёт ai.py — как у настоящих сервисов
        if method == "GET" and name == "hello":
            out = k.hello(clean_pc(qs.get("pc")))
        elif method == "POST" and name == "login":
            b = self.body_json()
            out = k.login(clean_pc(b.get("pc")), int(b.get("student_id") or 0))
        elif method == "GET" and name == "request":
            out = k.request_status(int(qs.get("id") or 0), qs.get("secret", ""))
        else:
            sess = k.live_session(token)
            if method == "GET" and name == "state":
                out = k.state_for(sess)
            elif method == "GET" and name == "lesson":
                out = k.lesson_for()
            elif method == "GET" and name == "task":
                out = k.lib.public_task(k.task(qs.get("id", "")))
            elif method == "POST" and name == "ai/ask":
                out = k.ai_ask(sess, self.body_json())
            elif method == "GET" and name == "ai/ticket":
                out = k.ai_ticket(sess, int(qs.get("id") or 0))
            elif method == "GET" and name == "solution":
                out = k.solution(sess, qs.get("id", ""))
            elif method == "POST" and name == "hint":
                b = self.body_json()
                out = k.hint(sess, str(b.get("task_id")), int(b.get("level") or 0))
            elif method == "POST" and name == "result":
                b = self.body_json()
                out = k.result(sess, str(b.get("task_id")), bool(b.get("ok")), str(b.get("summary", "")),
                               str(b.get("code", "")))
            elif method == "POST" and name == "rating":
                b = self.body_json()
                k.rating(sess, str(b.get("task_id")), str(b.get("rating")))
                out = {"ok": True}
            elif method == "POST" and name == "help":
                b = self.body_json()
                out = k.help(sess, str(b.get("text", "")), bool(b.get("cancel")))
            elif method == "POST" and name == "files":
                out = k.save_files(sess, self.body_json().get("files"))
            elif method == "POST" and name == "event":
                out = k.student_event(sess, self.body_json())
            elif method == "GET" and name == "play":
                if not k.play_allowed(sess["student_id"])[0]:
                    raise ApiError(403, k.play_allowed(sess["student_id"])[1])
                out = k.play_lobby(f"s:{sess['student_id']}", k.name(sess["student_id"]))
            elif method == "POST" and name.startswith("play/"):
                ok, why = k.play_allowed(sess["student_id"])
                if not ok and name != "play/leave":
                    raise ApiError(403, why)
                out = k.play_action(f"s:{sess['student_id']}", k.name(sess["student_id"]), name[5:], self.body_json())
            elif method == "GET" and name == "files":
                out = k.my_files(sess)
            elif method == "GET" and name == "idea":
                out = {"idea": k.idea_of(sess["student_id"])}
            elif method == "POST" and name == "idea":
                out = k.idea_save(sess, self.body_json())
            elif method == "GET" and name == "team":
                out = k.team_view(sess)
            elif method == "POST" and name.startswith("team/"):
                b = self.body_json()
                if name == "team/join":
                    k.team_join(sess, int(b.get("team_id") or 0))
                elif name == "team/leave":
                    k.team_leave(sess)
                elif name == "team/card":
                    k.team_card(sess, b)
                elif name == "team/plan":
                    k.team_plan(sess, str(b.get("plan", "")))
                elif name == "team/notice_ok":
                    k.team_notice(sess["student_id"], None)
                else:
                    raise ApiError(404, "Нет такой команды")
                out = k.team_view(sess)
            elif method == "POST" and name == "logout":
                k.close_session(sess["token"], "Ты вышел")
                k.s.log(sess["student_id"], "logout", {"pc": sess["pc"]})
                out = {"ok": True}
            else:
                raise ApiError(404, "Нет такой команды")
        k.s.db.commit()
        self.send_json(out)

    # --- API учителя ---
    def teacher_api(self, method: str, name: str, qs: dict) -> None:
        k = self.kurs
        if not self.is_local():
            raise ApiError(403, "Только на учительском компьютере")
        if method == "GET" and name == "whoami":
            return self.send_json({"has_password": k.s.has_password(), "logged_in": self.teacher_ok()})
        if method == "POST" and name == "setup":
            if k.s.has_password():
                raise ApiError(403, "Пароль уже задан")
            pw = str(self.body_json().get("password", ""))
            if len(pw) < 6:
                raise ApiError(400, "Пароль: не короче 6 символов")
            k.s.set_password(pw)
            return self.teacher_login_ok()
        if method == "POST" and name == "login":
            pw = str(self.body_json().get("password", ""))
            if not k.s.check_password(pw):
                time.sleep(0.5)
                raise ApiError(403, "Неверный пароль")
            return self.teacher_login_ok()
        if method == "POST" and name == "reset_password":
            p = k.s.password_file()
            if os.path.isfile(p):
                os.remove(p)
            return self.send_json({"ok": True})
        if not self.teacher_ok():
            raise ApiError(401, "Нужно войти")
        if method == "POST" and name == "logout":
            c = cookies.SimpleCookie(self.headers.get("Cookie") or "")
            k.s.teacher_tokens.pop(c["kurs_teacher"].value, None)
            return self.send_json({"ok": True}, headers={"Set-Cookie": "kurs_teacher=; Path=/; Max-Age=0"})
        if method == "GET" and name == "overview":
            out = k.overview()
        elif method == "GET" and name == "student":
            out = k.student_detail(int(qs.get("id") or 0))
        elif method == "GET" and name == "task":
            t = k.lib.tasks.get(qs.get("id", ""))
            if not t:
                raise ApiError(404, "Нет такого задания")
            out = dict(k.lib.public_task(t), hints=t.get("hints", []), solution=t["_solution"])
        elif method == "GET" and name == "ai":
            out = k.ai_overview(int(qs["student"]) if qs.get("student") else None)
        elif method == "GET" and name == "play":
            out = k.play_teacher()
        elif method == "GET" and name == "teams":
            out = k.teams_teacher()
        elif method == "GET" and name == "stage_code":
            out = k.stage_code(int(qs.get("n") or 0))
        elif method == "GET" and name == "export.csv":
            body = k.export_csv().encode("utf-8")
            return self.send_bytes(body, "text/csv; charset=utf-8", 200,
                                   {"Content-Disposition": 'attachment; filename="results.csv"'})
        elif method == "GET" and name in ("export_projects.json", "projects.json"):
            data = k.export_projects_data()
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            safe_name = re.sub(r"[^\w\-]", "_", str(data.get("group") or "class"))
            return self.send_bytes(body, "application/json; charset=utf-8", 200,
                                   {"Content-Disposition": content_disposition(f"projects_{safe_name}.json")})
        elif method == "GET" and name in ("export_projects.zip", "projects.zip"):
            body = k.export_projects_zip()
            data = k.export_projects_data()
            safe_name = re.sub(r"[^\w\-]", "_", str(data.get("group") or "class"))
            return self.send_bytes(body, "application/zip", 200,
                                   {"Content-Disposition": content_disposition(f"projects_{safe_name}.zip")})
        elif method == "POST":
            b = self.body_json()
            out = {"ok": True}
            if name == "group":
                out = k.save_group(str(b.get("name", "")), list(b.get("names") or []), b.get("id"))
            elif name == "group/delete":
                gid = int(b.get("id") or 0)
                if gid == k.s.get("group_id") and k.s.get("running"):
                    raise ApiError(400, "Сначала заверши занятие этой группы")
                k.s.ex("UPDATE students SET archived=1 WHERE group_id=?", (gid,))
                k.s.ex("DELETE FROM groups WHERE id=?", (gid,))
            elif name == "start":
                k.start(int(b.get("group_id") or 0), int(b.get("lesson") or 0))
            elif name == "continue":
                k.continue_class()
            elif name == "end":
                k.end()
            elif name == "open":
                ids = list(b.get("ids") or [])
                if b.get("step") is not None:
                    lesson = k.lesson()
                    ids = [i for i in lesson["task_ids"] if k.lib.tasks[i]["step"] <= int(b["step"])]
                if b.get("all"):
                    ids = k.lesson()["task_ids"]
                k.open_tasks(ids, bool(b.get("open", True)))
            elif name == "pause":
                k.s.set("paused", 1 if b.get("paused") else 0)
                k.s.set("pause_text", str(b.get("text") or "Пауза: смотрим на учителя")[:120])
            elif name == "timer":
                if b.get("clear"):
                    k.s.set("timer_end", None)
                elif b.get("add"):
                    end = k.s.get("timer_end") or time.time()
                    k.s.set("timer_end", max(end, time.time()) + 60 * int(b["add"]))
                else:
                    k.s.set("timer_end", time.time() + 60 * int(b.get("minutes") or 10))
                    k.s.set("timer_label", str(b.get("label") or "")[:60])
            elif name == "stage":
                n = int(b.get("stage") or 0)
                if n < 0 or n > len(k.lesson()["stages"]):
                    raise ApiError(400, "Нет такого этапа")
                k.s.set("stage", n)
            elif name == "request":
                k.decide(int(b.get("id") or 0), bool(b.get("approve")))
            elif name == "approve_all":
                for r in k.s.q("SELECT id FROM requests WHERE status='pending'"):
                    k.decide(r["id"], True)
            elif name == "help":
                k.s.ex("UPDATE help SET status=? WHERE id=?", ("going" if b.get("going") else "done", int(b.get("id") or 0)))
            elif name == "kick":
                sess = k.active_session_of(int(b.get("student_id") or 0))
                if sess:
                    k.close_session(sess["token"], "Учитель завершил твой сеанс")
            elif name == "reload":
                k.lib.load()
            elif name == "restart_clients":
                # все панели сохранят работу, обновятся и перезапустят окно VS Code
                k.s.set("restart_seq", (k.s.get("restart_seq") or 0) + 1)
                k.s.log(None, "restart_clients")
            elif name == "play/config":
                k.play_config(b)
            elif name == "play/stop_all":
                k.play.stop_all("Учитель остановил все партии")
            elif name == "play/end":
                k.play.end(str(b.get("match", "")), "Учитель остановил партию")
            elif name in ("play/invite", "play/answer", "play/cancel", "play/leave"):
                out = k.play_action(kurs_play.TEACHER, "Учитель", name[5:], b)
            elif name == "teams/create":
                k.teams_create(int(b.get("count") or 0), list(b.get("names") or []))
            elif name == "teams/config":
                k.teams_config(b)
            elif name == "teams/rename":
                k.teams_rename(int(b.get("team_id") or 0), str(b.get("name", "")))
            elif name == "teams/delete":
                k.teams_delete(None if b.get("all") else int(b.get("team_id") or 0))
            elif name == "teams/kick":
                k.teams_kick(int(b.get("student_id") or 0))
            elif name == "teams/assign":
                k.teams_assign(int(b.get("student_id") or 0), int(b.get("team_id") or 0))
            elif name == "unlock":
                k.unlock(int(b.get("student_id") or 0))
            elif name == "lock_on_paste":
                k.s.set("lock_on_paste", 1 if b.get("on") else 0)
            elif name == "close_clients":
                # все панели сохранят работу и закроют VS Code курса на компьютерах учеников
                k.s.set("close_seq", (k.s.get("close_seq") or 0) + 1)
                k.s.log(None, "close_clients")
            elif name == "restart_student":
                # то же самое, но только на компьютере одного ученика
                sid = int(b.get("student_id") or 0)
                if not k.student(sid):
                    raise ApiError(404, "Нет такого ученика")
                per = dict(k.s.get("restart_students") or {})
                per[str(sid)] = int(per.get(str(sid), 0)) + 1
                k.s.set("restart_students", per)
                k.s.log(sid, "restart_student")
            elif name == "ai/config":
                k.ai.save_config(b)
            elif name == "ai/mode":
                try:
                    k.ai.set_mode(str(b.get("mode")))
                except kurs_ai.AIError as e:
                    raise ApiError(400, str(e)) from None
            elif name == "ai/clear":
                k.s.ex("DELETE FROM ai_log")
            else:
                raise ApiError(404, "Нет такой команды")
        else:
            raise ApiError(404, "Нет такой команды")
        k.s.db.commit()
        self.send_json(out)

    def teacher_login_ok(self) -> None:
        tok = secrets.token_hex(24)
        self.kurs.s.teacher_tokens[tok] = time.time() + 12 * 3600
        self.send_json({"ok": True}, headers={
            "Set-Cookie": f"kurs_teacher={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age={12 * 3600}"})


def clean_pc(pc) -> str:
    pc = re.sub(r"[^\w.\- ]", "", str(pc or ""))[:40].strip()
    return pc or "без-имени"


def make_server(host: str, port: int, data_dir: str, tasks_dir: str | None = None, quiet: bool = False):
    store = Store(data_dir)
    lib = Library(tasks_dir or os.path.join(KURS, "tasks"), os.path.join(KURS, "content"))
    handler = type("KursHandler", (Handler,), {"kurs": Kurs(store, lib), "quiet": quiet})
    return ThreadingHTTPServer((host, port), handler)


def build_client() -> None:
    """Пересобирает панель VS Code и файлы для учеников (kurs/client/dist)."""
    sys.path.insert(0, os.path.join(KURS, "client"))
    try:
        import build  # noqa: PLC0415
        man = build.build()
        print(f"Панель для учеников собрана: версия {man['version']}.")
    except Exception as e:  # noqa: BLE001 — сервер работает и без свежей панели
        print(f"Не удалось собрать панель для учеников: {e!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Сервер курса «Чат-боты на Python»")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--data", default=os.path.expanduser("~/.kurs-server"))
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--reset-password", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)   # сообщения сразу видны, даже если вывод идёт в файл
    if a.reset_password:
        p = os.path.join(a.data, "teacher_password.json")
        if os.path.exists(p):
            os.remove(p)
        print("Пароль учителя сброшен. Задайте новый на странице учителя.")
        return
    build_client()
    try:
        srv = make_server(a.host, a.port, a.data, a.tasks)
    except OSError as e:
        if e.errno in (errno.EADDRINUSE, 10048):          # 10048 — тот же случай на Windows
            print(f"Порт {a.port} уже занят. Скорее всего, сервер курса уже запущен в другом окне —\n"
                  f"тогда просто откройте пульт: http://localhost:{a.port}/teacher\n"
                  "Перезапустить: остановите старый сервер (Ctrl+C в его окне"
                  + (", или: pkill -f kurs_server.py" if os.name != "nt" else "") + ") и запустите снова.\n"
                  f"Порт занят другой программой — запустите на другом: --port {a.port + 80}")
            sys.exit(1)
        raise
    ips = local_addresses()
    ip_str = f"http://{ips[0]}:{a.port}" if ips else f"http://localhost:{a.port}"
    bridge = srv.RequestHandlerClass.kurs.ai.check_bridge(force_fetch=True)
    if bridge and bridge.get("active"):
        ai_banner = f"🟢 [3] МОСТ ИИ / НЕЙРОСЕТЬ: Активен ({bridge.get('models', 'Gemini 3 Flash')}, прямой туннель)"
    elif srv.RequestHandlerClass.kurs.ai._configured():
        ai_banner = f"🟢 [3] МОСТ ИИ / НЕЙРОСЕТЬ: Активен ({srv.RequestHandlerClass.kurs.ai.cfg.get('provider')})"
    else:
        ai_banner = "🟡 [3] МОСТ ИИ / НЕЙРОСЕТЬ: Запасной режим (настройте ключ в пульте при необходимости)"

    print("\n" + "=" * 66)
    print("             🚦 СВЕТОФОР ГОТОВНОСТИ КУРСА К ЗАНЯТИЮ 🚦")
    print("=" * 66)
    print(f"🟢 [1] СЕРВЕР КУРСА     : Готов на порту {a.port} (версия {VERSION})")
    print(f"🟢 [2] СЕТЬ ДЛЯ КЛАССА   : {ip_str}")
    for extra_ip in ips[1:]:
        print(f"                           (резервный адрес: http://{extra_ip}:{a.port})")
    print(ai_banner)
    print(f"🟢 [4] ПУЛЬТ УЧИТЕЛЯ    : http://localhost:{a.port}/teacher")
    print("=" * 66)
    print("  Остановить сервер: нажмите Ctrl+C в этом окне\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")


if __name__ == "__main__":
    main()
