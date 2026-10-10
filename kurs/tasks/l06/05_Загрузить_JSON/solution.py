# Задание 5. Загрузить профиль из JSON
# Условие — в панели справа. Напиши программу ниже сам.

import json
import os

if os.path.exists("profile.json"):
    with open("profile.json", encoding="utf-8") as f:
        profile = json.load(f)
    print(f"Привет, {profile['имя']}! Как там {profile['хобби']}?")
else:
    print("Я тебя пока не знаю.")
