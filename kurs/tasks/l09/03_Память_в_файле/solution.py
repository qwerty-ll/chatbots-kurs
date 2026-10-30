# Задание 3. Память в файле
# Условие — в панели справа. Напиши программу ниже сам.

import json

try:
    with open("notes.json", encoding="utf-8") as f:
        notes = json.load(f)
except FileNotFoundError:
    notes = []

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    elif text == "/list":
        for i, note in enumerate(notes, 1):
            print(f"{i}. {note}")
    else:
        notes.append(text)
        with open("notes.json", "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False)
        print("Записал!")
