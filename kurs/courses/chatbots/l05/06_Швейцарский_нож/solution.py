# Задание 6. Агент «Швейцарский нож»
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool


def coin_flip():
    return random.choice(["Орёл", "Решка"])


def roll_dice(sides=6):
    return random.randint(1, int(sides))


def calculate(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b if b != 0 else "На ноль делить нельзя"
    return "Не знаю такого действия"


TOOLS = [
    make_tool("coin_flip", "Подбросить монетку: орёл или решка."),
    make_tool("roll_dice", "Бросить игральный кубик.",
              {"sides": {"type": "integer", "description": "Число граней, по умолчанию 6"}}),
    make_tool("calculate", "Точно посчитать: a op b, где op — один из + - * /.",
              {"a": {"type": "number", "description": "Первое число"},
               "op": {"type": "string", "description": "Действие: + - * /"},
               "b": {"type": "number", "description": "Второе число"}}, ["a", "op", "b"]),
]
FUNCTIONS = {
    "coin_flip": lambda args: coin_flip(),
    "roll_dice": lambda args: roll_dice(args.get("sides", 6)),
    "calculate": lambda args: calculate(args["a"], args["op"], args["b"]),
}

messages = [{"role": "system", "content": "Ты бот-помощник. Для монетки, кубика и счёта используй инструменты."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
