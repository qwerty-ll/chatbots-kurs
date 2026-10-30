# Задание 6. Журнал действий
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool

LOG = []


def coin_flip():
    result = random.choice(["Орёл", "Решка"])
    LOG.append(f"coin_flip -> {result}")
    return result


def roll_dice():
    result = random.randint(1, 6)
    LOG.append(f"roll_dice -> {result}")
    return result


TOOLS = [make_tool("coin_flip", "Подбросить монетку."), make_tool("roll_dice", "Бросить кубик на 6 граней.")]
FUNCTIONS = {"coin_flip": lambda args: coin_flip(), "roll_dice": lambda args: roll_dice()}
SYSTEM = "Ты ведущий игры. Монетку и кубик бросай только инструментами."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    if text == "/log":
        print("Журнал:")
        for row in LOG:
            print(row)
        continue
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
