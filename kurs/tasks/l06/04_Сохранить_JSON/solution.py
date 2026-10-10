# Задание 4. Сохранить профиль в JSON
# Условие — в панели справа. Напиши программу ниже сам.

import json

profile = {"имя": input("Как тебя зовут? "), "хобби": input("Твоё хобби: ")}
with open("profile.json", "w", encoding="utf-8") as f:
    json.dump(profile, f, ensure_ascii=False)
print("Сохранено!")
