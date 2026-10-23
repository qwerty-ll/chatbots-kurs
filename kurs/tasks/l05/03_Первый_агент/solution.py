# Задание 3. Первый агент: монетка
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool


def coin_flip():
    return random.choice(["Орёл", "Решка"])


TOOLS = [make_tool("coin_flip", "Подбросить монетку: выпадет орёл или решка.")]
FUNCTIONS = {"coin_flip": lambda args: coin_flip()}

messages = [{"role": "system", "content": "Ты бот-помощник. Если просят монетку — используй инструмент."},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
