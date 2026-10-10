# Задание 8. Счётчик запусков
# Условие — в панели справа. Напиши программу ниже сам.

import json
import os

FILE = "visits.json"
if os.path.exists(FILE):
    with open(FILE, encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"visits": 0}
data["visits"] += 1
with open(FILE, "w", encoding="utf-8") as f:
    json.dump(data, f)
print(f"Ты здесь в {data['visits']}-й раз")
