#!/usr/bin/env python3
"""Сбросить пароль учителя:  python3 reset_password.py [--data ПАПКА]"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Сбросить пароль учителя сервера курса")
    ap.add_argument("--data", default="~/.kurs-server", help="папка данных сервера (по умолчанию ~/.kurs-server)")
    args = ap.parse_args(argv)

    p = os.path.join(os.path.expanduser(args.data), "teacher_password.json")
    if os.path.isfile(p):
        try:
            os.remove(p)
            print("\n" + "=" * 50)
            print("✅ Пароль учителя успешно сброшен!")
            print("=" * 50)
            print("Теперь обновите страницу в браузере (F5):")
            print("http://localhost:8000/teacher")
            print("и задайте новый пароль.\n")
            return 0
        except OSError as e:
            print(f"❌ Ошибка при удалении файла пароля: {e}")
            return 1
    else:
        print(f"\nℹ️ Пароль учителя не установлен (файл не найден: {p}).")
        print("Откройте http://localhost:8000/teacher в браузере и задайте новый пароль.\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
