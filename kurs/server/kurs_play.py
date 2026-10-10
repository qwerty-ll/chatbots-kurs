"""Игры по сети класса: лобби, вызовы и партии — шахматы, аэрохоккей, морской бой.

Всё хранится в памяти (перезапуск сервера заканчивает партии). Правила игр считают сами игроки
(панель ученика и пульт учителя), сервер только сводит соперников и пересылает ходы:
- лобби и вызовы — обычными запросами (панель и так опрашивает сервер);
- ходы — по WebSocket (стандартный Python, без библиотек): аэрохоккею нужно ~30 сообщений в секунду.
Ходы пошаговых игр сервер запоминает, чтобы после перезапуска окна партию можно было продолжить.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
import threading
import time

GAMES = {"chess": "Шахматы", "hockey": "Аэрохоккей", "battleship": "Морской бой"}
TEACHER = "t"                 # ключ учителя в лобби; ученики — "s:<id>"
SEEN_TTL = 12                 # секунд: игрок в лобби, если его панель недавно обращалась к серверу
INVITE_TTL = 45               # секунд живёт вызов без ответа
LOGGED = ("move", "ready", "shot", "result", "resign", "over")   # такие сообщения повторяем после переподключения
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class PlayError(Exception):
    """Понятная игроку ошибка."""


class Play:
    def __init__(self):
        self.lock = threading.RLock()
        self.seen: dict[str, tuple[str, float]] = {}
        self.invites: dict[str, dict] = {}
        self.matches: dict[str, dict] = {}

    # ---------- кто в лобби ----------
    def touch(self, key: str, name: str) -> None:
        with self.lock:
            self.seen[key] = (name, time.time())

    def forget(self, key: str) -> None:
        with self.lock:
            self.seen.pop(key, None)

    def online(self) -> dict[str, str]:
        now = time.time()
        with self.lock:
            return {k: n for k, (n, t) in self.seen.items() if now - t < SEEN_TTL}

    def match_of(self, key: str) -> dict | None:
        with self.lock:
            for m in self.matches.values():
                if key in m["players"] and not m["over"]:
                    return m
        return None

    def _gc(self) -> None:
        now = time.time()
        for i, inv in list(self.invites.items()):
            if now - inv["ts"] > INVITE_TTL:
                del self.invites[i]
        for i, m in list(self.matches.items()):
            if m["over"] and now - m["over"] > 600:
                del self.matches[i]

    # ---------- вызовы ----------
    def invite(self, frm: str, frm_name: str, to: str, game: str, allowed: dict[str, str]) -> str:
        """allowed — кого сейчас можно вызвать (ключ → имя): решает сервер курса по правилам учителя."""
        if game not in GAMES:
            raise PlayError("Нет такой игры")
        with self.lock:
            self._gc()
            if to == frm:
                raise PlayError("Нельзя вызвать самого себя")
            if to not in allowed or to not in self.online():
                raise PlayError("Этот игрок сейчас не может играть")
            if self.match_of(frm):
                raise PlayError("Ты уже в партии")
            if self.match_of(to):
                raise PlayError(f"{allowed[to]} уже играет")
            for inv in self.invites.values():
                if inv["frm"] == frm and inv["to"] == to:
                    raise PlayError("Вызов уже отправлен — ждём ответа")
            iid = secrets.token_hex(4)
            self.invites[iid] = {"id": iid, "frm": frm, "frm_name": frm_name, "to": to, "to_name": allowed[to],
                                 "game": game, "ts": time.time()}
            return iid

    def answer(self, iid: str, key: str, accept: bool) -> dict | None:
        with self.lock:
            self._gc()
            inv = self.invites.get(iid)
            if not inv or inv["to"] != key:
                raise PlayError("Вызов уже не действует")
            del self.invites[iid]
            if not accept:
                return None
            if self.match_of(inv["frm"]) or self.match_of(key):
                raise PlayError("Кто-то из вас уже играет")
            # вызов «отменяет» остальные вызовы этих двоих
            for i, x in list(self.invites.items()):
                if {x["frm"], x["to"]} & {inv["frm"], key}:
                    del self.invites[i]
            return self._new_match(inv["game"], [inv["frm"], key], [inv["frm_name"], inv["to_name"]])

    def cancel(self, iid: str, key: str) -> None:
        with self.lock:
            inv = self.invites.get(iid)
            if inv and key in (inv["frm"], inv["to"]):
                del self.invites[iid]

    def _new_match(self, game: str, players: list[str], names: list[str]) -> dict:
        mid = secrets.token_hex(6)
        m = {"id": mid, "game": game, "players": players, "names": names, "log": [], "socks": [None, None],
             "send_locks": [threading.Lock(), threading.Lock()], "created": time.time(), "over": 0, "result": ""}
        self.matches[mid] = m
        return m

    # ---------- партии ----------
    def end(self, mid: str, reason: str) -> None:
        with self.lock:
            m = self.matches.get(mid)
            if not m or m["over"]:
                return
            m["over"] = time.time()
            m["result"] = reason
        self.broadcast(m, {"type": "stopped", "reason": reason})

    def leave(self, key: str, reason: str) -> None:
        m = self.match_of(key)
        if m:
            self.end(m["id"], reason)

    def stop_all(self, reason: str) -> None:
        with self.lock:
            ids = [m["id"] for m in self.matches.values() if not m["over"]]
            self.invites.clear()
        for mid in ids:
            self.end(mid, reason)

    def info(self, key: str) -> dict:
        """Что видит игрок: входящие и исходящие вызовы, текущая партия."""
        with self.lock:
            self._gc()
            m = self.match_of(key)
            return {
                "invites_in": [{"id": i["id"], "from": i["frm"], "name": i["frm_name"], "game": i["game"]}
                               for i in self.invites.values() if i["to"] == key],
                "invites_out": [{"id": i["id"], "to": i["to"], "name": i["to_name"], "game": i["game"]}
                                for i in self.invites.values() if i["frm"] == key],
                "match": self.public_match(m, key) if m else None,
            }

    def public_match(self, m: dict, key: str | None = None) -> dict:
        out = {"id": m["id"], "game": m["game"], "names": m["names"], "created": m["created"],
               "connected": [s is not None for s in m["socks"]], "moves": sum(1 for x in m["log"] if x.get("type") == "move")}
        if key is not None:
            out["you"] = m["players"].index(key)
        return out

    def list_matches(self) -> list[dict]:
        with self.lock:
            return [self.public_match(m) for m in self.matches.values() if not m["over"]]

    def busy(self) -> set[str]:
        with self.lock:
            return {p for m in self.matches.values() if not m["over"] for p in m["players"]}

    # ---------- WebSocket ----------
    def broadcast(self, m: dict, msg: dict, skip: int | None = None) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        for i in (0, 1):
            if i != skip and m["socks"][i] is not None:
                try:
                    with m["send_locks"][i]:
                        ws_send(m["socks"][i], data)
                except OSError:
                    m["socks"][i] = None

    def serve(self, mid: str, key: str, wfile, rfile) -> None:
        """Цикл одного подключения игрока к партии: пересылаем сообщения сопернику."""
        with self.lock:
            m = self.matches.get(mid)
            if not m or key not in m["players"]:
                ws_send(wfile, json.dumps({"type": "stopped", "reason": "Партия уже закончилась"}, ensure_ascii=False))
                return
            me = m["players"].index(key)
            m["socks"][me] = wfile
        with m["send_locks"][me]:
            ws_send(wfile, json.dumps({"type": "hello", "you": me, "names": m["names"], "game": m["game"],
                                       "log": m["log"], "over": m["result"] if m["over"] else ""}, ensure_ascii=False))
        self.broadcast(m, {"type": "joined", "who": me}, skip=me)
        try:
            while True:
                op, payload = ws_read(rfile)
                if op == 8:                       # закрытие
                    break
                if op == 9:                       # ping → pong
                    with m["send_locks"][me]:
                        ws_send(wfile, payload, opcode=10)
                    continue
                if op != 1 or m["over"]:
                    continue
                try:
                    msg = json.loads(payload.decode("utf-8"))
                except ValueError:
                    continue
                if not isinstance(msg, dict) or msg.get("type") == "ping":
                    continue
                msg["by"] = me                    # кто прислал (номер игрока); «from» занят ходами шахмат
                if msg.get("type") in LOGGED:
                    with self.lock:
                        m["log"].append(msg)
                        if len(m["log"]) > 2000:
                            m["log"] = m["log"][-2000:]
                self.broadcast(m, msg, skip=me)
                if msg.get("type") in ("resign", "over"):
                    with self.lock:
                        m["over"] = m["over"] or time.time()
                        m["result"] = m["result"] or msg.get("text", "Партия окончена")
        except (OSError, ValueError, struct.error):
            pass
        finally:
            if m["socks"][me] is wfile:
                m["socks"][me] = None
            self.broadcast(m, {"type": "gone", "who": me})


# ---------- минимальный WebSocket (RFC 6455): только то, что нужно игре ----------
def ws_accept(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def ws_send(wfile, data, opcode: int = 1) -> None:
    payload = data.encode("utf-8") if isinstance(data, str) else data
    n = len(payload)
    if n < 126:
        head = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 65536:
        head = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    wfile.write(head + payload)
    wfile.flush()


def _read_exact(rfile, n: int) -> bytes:
    buf = rfile.read(n)
    if buf is None or len(buf) < n:
        raise OSError("соединение закрыто")
    return buf


def ws_read(rfile) -> tuple[int, bytes]:
    """Одно сообщение от браузера (кадры от клиента всегда с маской)."""
    data = b""
    op = None
    while True:
        b1, b2 = _read_exact(rfile, 2)
        fin, opcode = b1 & 0x80, b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", _read_exact(rfile, 2))[0]
        elif n == 127:
            n = struct.unpack("!Q", _read_exact(rfile, 8))[0]
        if n > 1 << 20:
            raise ValueError("слишком большое сообщение")
        mask = _read_exact(rfile, 4) if b2 & 0x80 else b"\0\0\0\0"
        chunk = bytes(c ^ mask[i % 4] for i, c in enumerate(_read_exact(rfile, n)))
        if opcode >= 8:                       # служебные кадры приходят целиком
            return opcode, chunk
        if op is None:
            op = opcode
        data += chunk
        if fin:
            return op, data
