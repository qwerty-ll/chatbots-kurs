"""Integration & regression tests for kurs_server.py, kurs_ai.py, and kurs_play.py."""
from __future__ import annotations

import http.client
import io
import json
import os
import struct
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(ROOT, "kurs", "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import kurs_ai  # noqa: E402
import kurs_play  # noqa: E402
import kurs_server  # noqa: E402


class ServerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = kurs_server.make_server("127.0.0.1", 0, self.tmp.name, quiet=True)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.cookie: str | None = None

    def tearDown(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()
        kurs = self.srv.RequestHandlerClass.kurs
        kurs.play.shutdown()
        kurs.ai.shutdown()
        kurs.s.close_all()
        self.tmp.cleanup()

    def req(
        self,
        method: str,
        path: str,
        body: dict | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        hdrs = dict(headers or {})
        if self.cookie and "Cookie" not in hdrs:
            hdrs["Cookie"] = self.cookie
        raw: bytes | None = None
        if isinstance(body, dict):
            raw = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        elif isinstance(body, bytes):
            raw = body
        conn.request(method, path, body=raw, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return resp.status, resp_headers, data

    def login_teacher(self, password: str = "secret123") -> None:
        status, hdrs, _ = self.req("POST", "/tapi/setup", {"password": password})
        self.assertEqual(status, 200)
        sc = hdrs.get("set-cookie", "")
        self.assertIn("kurs_teacher=", sc)
        self.cookie = sc.split(";", 1)[0]

    def test_teacher_and_projector_pages_serve_200(self) -> None:
        for path in ("/teacher", "/teacher/projector.html"):
            status, _, data = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn(b"<html", data.lower())

    def test_duplicate_group_rename_returns_400_not_500(self) -> None:
        self.login_teacher()
        s1, _, _ = self.req("POST", "/tapi/group", {"name": "Alpha", "names": ["Аня", "Боря"]})
        self.assertEqual(s1, 200)
        s2, _, _ = self.req("POST", "/tapi/group", {"name": "Beta", "names": ["Вася"]})
        self.assertEqual(s2, 200)

        _, _, ov = self.req("GET", "/tapi/overview")
        groups = json.loads(ov)["groups"]
        beta = next(g for g in groups if g["name"] == "Beta")

        s3, _, body = self.req("POST", "/tapi/group", {"id": beta["id"], "name": "Alpha", "names": ["Вася"]})
        self.assertEqual(s3, 400, body.decode("utf-8", "replace"))

    def test_teams_delete_zero_does_not_wipe_all_teams(self) -> None:
        self.login_teacher()
        self.req("POST", "/tapi/group", {"name": "G1", "names": ["Аня", "Боря"]})
        _, _, ov = self.req("GET", "/tapi/overview")
        gid = json.loads(ov)["groups"][0]["id"]
        self.req("POST", "/tapi/start", {"group_id": gid, "lesson": 8})

        st_c, _, _ = self.req("POST", "/tapi/teams/create", {"count": 2, "names": ["Team One", "Team Two"]})
        self.assertEqual(st_c, 200)
        _, _, tbody0 = self.req("GET", "/tapi/teams")
        initial_ids = {t["id"] for t in json.loads(tbody0)["teams"]}
        self.assertEqual(len(initial_ids), 2)

        # Missing or 0 team_id without all=True must return 400 and leave teams intact
        for payload in ({}, {"team_id": 0}, {"team_id": -1}):
            st, _, _ = self.req("POST", "/tapi/teams/delete", payload)
            self.assertEqual(st, 400)

        _, _, tbody = self.req("GET", "/tapi/teams")
        team_ids = {t["id"] for t in json.loads(tbody)["teams"]}
        self.assertEqual(team_ids, initial_ids)

    def test_reset_lesson_omitting_group_id_does_not_wipe_other_groups(self) -> None:
        self.login_teacher()
        self.req("POST", "/tapi/group", {"name": "G1", "names": ["Аня"]})
        self.req("POST", "/tapi/group", {"name": "G2", "names": ["Боря"]})
        _, _, ov = self.req("GET", "/tapi/overview")
        groups = {g["name"]: g["id"] for g in json.loads(ov)["groups"]}

        kurs = self.srv.RequestHandlerClass.kurs
        s1 = kurs.s.one("SELECT id FROM students WHERE group_id=?", (groups["G1"],))["id"]
        s2 = kurs.s.one("SELECT id FROM students WHERE group_id=?", (groups["G2"],))["id"]
        kurs.s.ex("INSERT INTO results(student_id,task_id,status,attempts,updated) VALUES(?,?,?,?,1.0)", (s1, "t1", "ok", 1))
        kurs.s.ex("INSERT INTO results(student_id,task_id,status,attempts,updated) VALUES(?,?,?,?,1.0)", (s2, "t1", "ok", 1))
        kurs.s.commit()

        self.req("POST", "/tapi/start", {"group_id": groups["G1"], "lesson": 1})
        st, _, _ = self.req("POST", "/tapi/reset_lesson", {"lesson": 1})
        self.assertEqual(st, 200)

        # G2's result must still exist
        r2 = kurs.s.one("SELECT * FROM results WHERE student_id=?", (s2,))
        self.assertIsNotNone(r2)

    def test_reset_password_requires_json_and_clears_tokens(self) -> None:
        self.login_teacher("pass1234")
        # Form-style CSRF POST without application/json must be rejected
        st, _, _ = self.req(
            "POST",
            "/tapi/reset_password",
            body=b"x=1",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": ""},
        )
        self.assertEqual(st, 415)

        # Valid JSON POST resets password AND invalidates existing teacher token
        st2, _, _ = self.req("POST", "/tapi/reset_password", body={})
        self.assertEqual(st2, 200)

        st3, _, _ = self.req("GET", "/tapi/overview")
        self.assertEqual(st3, 401)

    def test_save_files_rejects_windows_and_posix_path_traversal(self) -> None:
        self.login_teacher()
        self.req("POST", "/tapi/group", {"name": "Sec", "names": ["Аня"]})
        _, _, ov = self.req("GET", "/tapi/overview")
        gid = json.loads(ov)["groups"][0]["id"]
        self.req("POST", "/tapi/start", {"group_id": gid, "lesson": 1})

        kurs = self.srv.RequestHandlerClass.kurs
        sid = kurs.s.one("SELECT id FROM students WHERE group_id=?", (gid,))["id"]
        kurs.save_files(
            {"student_id": sid},
            [
                {"path": "..\\evil.py", "content": "x"},
                {"path": "C:\\Windows\\win.ini", "content": "x"},
                {"path": "/etc/passwd", "content": "x"},
                {"path": "a/../../escape.py", "content": "x"},
                {"path": "Занятие_1/ok.py", "content": "print(1)"},
            ],
        )
        kurs.s.commit()
        rows = kurs.s.q("SELECT path FROM files WHERE student_id=?", (sid,))
        self.assertEqual([r["path"] for r in rows], ["Занятие_1/ok.py"])

    def test_negative_content_length_returns_400(self) -> None:
        self.login_teacher()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/tapi/group")
        conn.putheader("Cookie", self.cookie or "")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "-5")
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)

    def test_studio_code_and_clear_release_endpoints(self) -> None:
        self.login_teacher()
        self.req("POST", "/tapi/group", {"name": "Studio", "names": ["Аня"]})
        _, _, ov = self.req("GET", "/tapi/overview")
        gid = json.loads(ov)["groups"][0]["id"]
        self.req("POST", "/tapi/start", {"group_id": gid, "lesson": 8})

        self.req("POST", "/tapi/teams/create", {"count": 1, "names": ["Команда X"]})
        _, _, tbody = self.req("GET", "/tapi/teams")
        tid = json.loads(tbody)["teams"][0]["id"]

        kurs = self.srv.RequestHandlerClass.kurs
        sid = kurs.s.one("SELECT id FROM students WHERE group_id=?", (gid,))["id"]
        kurs.teams_assign(sid, tid)
        kurs.s.commit()

        # Submit a team build via studio_action
        rev = kurs.game_studio(tid)["revision"]
        kurs.studio_action(
            {"student_id": sid},
            "submit",
            {
                "revision": rev,
                "mode": "template",
                "code": "print('hello game')\n",
                "filename": "team_walk.py",
                "menu": {"title": "Бродилка X", "levels": 2},
            },
        )
        kurs.s.commit()

        st, _, raw = self.req("GET", f"/tapi/teams/studio_code?team_id={tid}")
        self.assertEqual(st, 200, raw.decode("utf-8", "replace"))
        data = json.loads(raw)
        self.assertEqual(data["team_id"], tid)
        self.assertIn("Бродилка команды", data["code"])

        st2, _, _ = self.req("POST", "/tapi/teams/clear_release", {"team_id": tid})
        self.assertEqual(st2, 200)

        st3, _, raw3 = self.req("GET", f"/tapi/teams/studio_code?team_id={tid}")
        self.assertEqual(st3, 200)
        self.assertIsNone(json.loads(raw3)["release"])

    def test_ai_bridge_does_not_override_pause_or_offline_mode(self) -> None:
        kurs = self.srv.RequestHandlerClass.kurs
        kurs.ai.set_mode("pause")
        kurs.ai.check_bridge(force_fetch=True)
        self.assertEqual(kurs.ai.cfg["mode"], "pause")

        kurs.ai.set_mode("offline")
        kurs.ai.check_bridge(force_fetch=True)
        self.assertEqual(kurs.ai.cfg["mode"], "offline")

    def test_ws_read_rejects_oversized_fragmented_frames(self) -> None:
        # Two 600KB frames (> 1MB total) with FIN=0 then FIN=1
        chunk = b"a" * (600 * 1024)
        mask = b"\x01\x02\x03\x04"
        masked = bytes(b ^ mask[i & 3] for i, b in enumerate(chunk))

        def make_frame(fin: bool, opcode: int) -> bytes:
            b0 = (0x80 if fin else 0x00) | opcode
            b1 = 0x80 | 127
            return bytes([b0, b1]) + struct.pack("!Q", len(chunk)) + mask + masked

        stream = io.BytesIO(make_frame(False, 1) + make_frame(True, 0))
        with self.assertRaises(ValueError):
            kurs_play.ws_read(stream)


if __name__ == "__main__":
    unittest.main()
