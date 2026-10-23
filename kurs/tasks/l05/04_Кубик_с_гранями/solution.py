# Задание 4. Инструмент с параметром: кубик
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool


def roll_dice(sides=6):
    return random.randint(1, int(sides))


TOOLS = [make_tool("roll_dice", "Бросить игральный кубик.",
                   {"sides": {"type": "integer", "description": "Число граней, по умолчанию 6"}})]
FUNCTIONS = {"roll_dice": lambda args: roll_dice(args.get("sides", 6))}

messages = [{"role": "system", "content": "Ты бот-помощник. Для бросков используй инструмент."},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
