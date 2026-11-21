"""Автотесты всех заданий курсов: эталоны, шаблоны и заголовки конструкций."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_DIR = REPO_ROOT / "kurs" / "checker"
COURSES_DIR = REPO_ROOT / "kurs" / "courses"

if str(CHECKER_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKER_DIR))

import kurs_check  # noqa: E402


def discover_tasks() -> list[Path]:
    return sorted(COURSES_DIR.glob("*/*/*/task.json"))


class TestCourses(unittest.TestCase):
    def test_all_solutions_pass_and_starters_fail(self) -> None:
        task_files = discover_tasks()
        self.assertGreaterEqual(len(task_files), 74, f"Ожидалось не меньше 74 заданий, найдено {len(task_files)}")

        for task_file in task_files:
            task_dir = task_file.parent
            rel = task_dir.relative_to(COURSES_DIR)
            with self.subTest(task=str(rel)):
                task, loaded_dir = kurs_check.load_task(str(task_file))
                sol_path = task_dir / "solution.py"
                start_path = task_dir / "start.py"
                self.assertTrue(sol_path.is_file(), f"Нет solution.py в {rel}")
                self.assertTrue(start_path.is_file(), f"Нет start.py в {rel}")

                sol_code = sol_path.read_text(encoding="utf-8")
                sol_res = kurs_check.check(
                    task,
                    sol_code,
                    filename=task.get("file", "solution.py"),
                    task_dir=loaded_dir,
                    src_dir=loaded_dir,
                )
                self.assertTrue(
                    sol_res["ok"],
                    f"solution.py не прошёл проверку для {rel}: {sol_res.get('summary')} | "
                    f"error={sol_res.get('error')} | "
                    f"failed={[i for i in sol_res.get('items', []) if not i['ok']]}",
                )

                start_code = start_path.read_text(encoding="utf-8")
                start_res = kurs_check.check(
                    task,
                    start_code,
                    filename=task.get("file", "start.py"),
                    task_dir=loaded_dir,
                    src_dir=loaded_dir,
                )
                self.assertFalse(
                    start_res["ok"],
                    f"start.py неожиданно прошёл проверку для {rel}!",
                )

    def test_all_structure_needs_have_feature_titles(self) -> None:
        task_files = discover_tasks()
        missing: list[tuple[str, str]] = []
        for task_file in task_files:
            rel = str(task_file.parent.relative_to(COURSES_DIR))
            task = json.loads(task_file.read_text(encoding="utf-8"))
            for rule in task.get("structure", []):
                if "need" not in rule or rule.get("title"):
                    continue
                need = rule["need"]
                alts = need if isinstance(need, list) else [need]
                for key in alts:
                    if key not in kurs_check.FEATURE_TITLES:
                        missing.append((rel, key))
        self.assertEqual(
            missing,
            [],
            f"Найдены ключи structure.need без заголовка в FEATURE_TITLES: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
