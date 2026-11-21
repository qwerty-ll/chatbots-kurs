"""Автотесты для kurs_check.py, песочницы Код/Наш_бот.py и Код/agent.py."""
from __future__ import annotations

import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_DIR = REPO_ROOT / "kurs" / "checker"
CODE_DIR = REPO_ROOT / "Код"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import kurs_check  # noqa: E402


def _load_code_modules():
    """Загружает Код/agent.py и Код/Наш_бот.py с заглушкой ai (без .env)."""
    fake_ai = types.ModuleType("ai")
    fake_ai.chat = lambda *args, **kwargs: None  # type: ignore[attr-defined]

    saved_ai = sys.modules.get("ai")
    saved_agent = sys.modules.get("agent")
    try:
        sys.modules["ai"] = fake_ai
        agent_spec = importlib.util.spec_from_file_location("agent", CODE_DIR / "agent.py")
        assert agent_spec and agent_spec.loader
        agent_mod = importlib.util.module_from_spec(agent_spec)
        sys.modules["agent"] = agent_mod
        agent_spec.loader.exec_module(agent_mod)

        bot_spec = importlib.util.spec_from_file_location("nash_bot_test", CODE_DIR / "Наш_бот.py")
        assert bot_spec and bot_spec.loader
        bot_mod = importlib.util.module_from_spec(bot_spec)
        bot_spec.loader.exec_module(bot_mod)
        return agent_mod, bot_mod
    finally:
        if saved_ai is not None:
            sys.modules["ai"] = saved_ai
        else:
            sys.modules.pop("ai", None)
        if saved_agent is not None:
            sys.modules["agent"] = saved_agent
        else:
            sys.modules.pop("agent", None)


class TestKursCheckFixes(unittest.TestCase):
    def test_multi_import_detected(self) -> None:
        code = "import os, random, time\n"
        feats = kurs_check._features(ast.parse(code), code)
        self.assertIn("import:os", feats)
        self.assertIn("import:random", feats)
        self.assertIn("import:time", feats)

    def test_empty_list_detected(self) -> None:
        code = "items = []\n"
        feats = kurs_check._features(ast.parse(code), code)
        self.assertIn("list", feats)

    def test_nonzero_exit_code_fails(self) -> None:
        task = {
            "id": "test-exit",
            "tests": [{"input": [], "expect": ["ok"]}],
        }
        code = 'import sys\nprint("ok")\nsys.exit(1)\n'
        res = kurs_check.check(task, code)
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["items"]), 1)
        self.assertFalse(res["items"][0]["ok"])
        self.assertIn("1", res["items"][0]["message"])

    def test_blanks_in_strings_and_comments_ignored(self) -> None:
        task = {
            "id": "test-blanks",
            "tests": [{"input": [], "expect": ["___"]}],
        }
        code = '# комментарий с ___\nprint("___")\n'
        res = kurs_check.check(task, code)
        self.assertTrue(res["ok"], f"Неожиданная ошибка: {res}")

        bad_code = "x = ___\nprint(x)\n"
        bad_res = kurs_check.check(task, bad_code)
        self.assertFalse(bad_res["ok"])
        self.assertIsNotNone(bad_res["error"])
        self.assertIn("пропуск", bad_res["error"]["title"].lower())

    def test_dialog_markers_not_split_on_long_output(self) -> None:
        task = {
            "id": "test-dialog",
            "tests": [{"input": ["привет"], "expect": ["ответ: привет"]}],
        }
        code = (
            'print("A" * 3500)\n'
            'msg = input("Скажи что-нибудь: ")\n'
            'print("ответ:", msg)\n'
        )
        res = kurs_check.check(task, code)
        self.assertTrue(res["ok"], f"Неожиданная ошибка: {res}")
        dialog = res["items"][0]["dialog"]
        self.assertTrue(any(who == "you" and text == "привет" for who, text in dialog))
        for _, text in dialog:
            for ctrl in ("\x01", "\x02", "\x03", "\x04"):
                self.assertNotIn(ctrl, text)


class TestNashBotSandbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent_mod, cls.bot_mod = _load_code_modules()

    def test_rejects_open(self) -> None:
        code = 'def f(args):\n    return open("/etc/passwd").read()\n'
        self.assertIsNotNone(self.bot_mod.problem_in(code))

    def test_rejects_input_inside_def_but_allows_in_main(self) -> None:
        bad = 'def f(args):\n    return input("?")\n'
        self.assertIsNotNone(self.bot_mod.problem_in(bad))

        good = (
            'def f(args):\n'
            '    return "ok"\n'
            'if __name__ == "__main__":\n'
            '    x = input("test: ")\n'
            '    print(f({}))\n'
        )
        self.assertIsNone(self.bot_mod.problem_in(good))

    def test_rejects_dunder_attributes(self) -> None:
        code = 'def f(args):\n    return f.__globals__["__builtins__"]\n'
        self.assertIsNotNone(self.bot_mod.problem_in(code))

    def test_rejects_top_level_print(self) -> None:
        code = 'print("hello")\ndef f(args):\n    return "ok"\n'
        self.assertIsNotNone(self.bot_mod.problem_in(code))

    def test_allows_valid_tool_file(self) -> None:
        code = (
            '"""Мои инструменты."""\n'
            'import random\n'
            'from agent import make_tool\n\n'
            'def roll(args):\n'
            '    return random.randint(1, 6)\n\n'
            'TOOLS = [make_tool("roll", "Бросить кубик")]\n'
            'FUNCTIONS = {"roll": roll}\n'
        )
        self.assertIsNone(self.bot_mod.problem_in(code))

    def test_has_blanks_tokenize(self) -> None:
        self.assertFalse(self.bot_mod.has_blanks('# ___\nx = "___"\n'))
        self.assertTrue(self.bot_mod.has_blanks("x = ___\n"))


class TestAgentMalformedJson(unittest.TestCase):
    def test_malformed_tool_arguments_do_not_crash(self) -> None:
        agent_mod, _ = _load_code_modules()
        responses = [
            types.SimpleNamespace(
                content="",
                tool_calls=[
                    types.SimpleNamespace(
                        id="call_bad",
                        type="function",
                        function=types.SimpleNamespace(name="roll", arguments="{broken json"),
                    )
                ],
            ),
            types.SimpleNamespace(content="Исправленный ответ", tool_calls=None),
        ]

        def fake_chat(messages, tools=None):
            return responses.pop(0)

        agent_mod.chat = fake_chat
        messages = [{"role": "user", "content": "Брось кубик"}]
        answer = agent_mod.agent_answer(messages, [], {"roll": lambda args: "6"})
        self.assertEqual(answer, "Исправленный ответ")
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertIn("JSON", tool_msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()
