# Задание 3. Читаем JSON
# Условие — в панели справа. Напиши программу ниже сам.

import json

text = input("JSON: ")
try:
    data = json.loads(text)
    print(f"{data['name']}, {data['age']} лет")
except json.JSONDecodeError:
    print("Это не JSON")
