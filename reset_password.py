#!/usr/bin/env python3
"""Сбросить пароль учителя:  python3 reset_password.py"""
import os
import sys

p = os.path.expanduser("~/.kurs-server/teacher_password.json")
if os.path.isfile(p):
    try:
        os.remove(p)
        print("\n" + "=" * 50)
        print("✅ Пароль учителя успешно сброшен!")
        print("=" * 50)
        print("Теперь обновите страницу в браузере (F5):")
        print("http://localhost:8000/teacher")
        print("и задайте новый пароль.\n")
    except Exception as e:
        print(f"❌ Ошибка при удалении файла пароля: {e}")
        sys.exit(1)
else:
    print("\nℹ️ Пароль учителя не установлен (файл отсутствует).")
    print("Откройте http://localhost:8000/teacher в браузере и задайте новый пароль.\n")
