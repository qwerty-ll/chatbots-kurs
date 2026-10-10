# Задание 6. Бот помнит имя между запусками
# Условие — в панели справа. Напиши программу ниже сам.

import json
import os

FILE = "memory.json"
if os.path.exists(FILE):
    with open(FILE, encoding="utf-8") as f:
        memory = json.load(f)
    print(f"С возвращением, {memory['имя']}!")
else:
    name = input("Как тебя зовут? ").strip()
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({"имя": name}, f, ensure_ascii=False)
    print(f"Запомнил, {name}!")
