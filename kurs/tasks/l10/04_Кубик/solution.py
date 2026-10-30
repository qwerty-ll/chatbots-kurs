# Задание 4. Кубик с необязательными гранями
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool


def roll_dice(sides):
    return random.randint(1, sides)


TOOLS = [make_tool("roll_dice", "Бросить кубик. Если число граней не сказали — обычный на 6.",
                   {"sides": {"type": "integer", "description": "Число граней"}})]
FUNCTIONS = {"roll_dice": lambda args: roll_dice(args.get("sides", 6))}
SYSTEM = "Ты ведущий настольной игры. Кубики бросай только инструментом roll_dice."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
