# Задание 5. Вызов инструмента вручную
# Условие — в панели справа. Напиши программу ниже сам.

import json

FUNCTIONS = {
    "add": lambda args: args["a"] + args["b"],
    "hello": lambda args: f"Привет, {args['name']}!",
}

call = json.loads(input("Вызов: "))
name = call["name"]
if name in FUNCTIONS:
    print("Результат:", FUNCTIONS[name](call["args"]))
else:
    print("Нет инструмента", name)
