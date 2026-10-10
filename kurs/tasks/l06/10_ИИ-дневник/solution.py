# Задание 10. ИИ-дневник
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask

import json
import os
from datetime import date

from ai import ask

FILE = "diary.json"
if os.path.exists(FILE):
    with open(FILE, encoding="utf-8") as f:
        diary = json.load(f)
else:
    diary = []

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    elif text.startswith("/add "):
        entry = {"дата": date.today().strftime("%d.%m.%Y"), "текст": text[5:]}
        diary.append(entry)
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(diary, f, ensure_ascii=False)
        print(ask(f"Тепло прокомментируй запись в дневнике одним предложением: {entry['текст']}"))
    elif text == "/list":
        for entry in diary:
            print(f"{entry['дата']}: {entry['текст']}")
