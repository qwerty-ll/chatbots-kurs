# Задание 2. Анкета в JSON
# Условие — в панели справа. Напиши программу ниже сам.

import json

name = input("Имя: ").strip()
age = int(input("Возраст: "))
data = {"name": name, "age": age}
print(json.dumps(data, ensure_ascii=False))
