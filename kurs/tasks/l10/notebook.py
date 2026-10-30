# Тетрадь урока 10. Агент выбирает инструмент
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Команды в словаре
import random


def cmd_hello():
    return "Привет!"


def cmd_coin():
    return random.choice(["Орёл", "Решка"])


COMMANDS = {"/hello": cmd_hello, "/coin": cmd_coin}
print(COMMANDS["/coin"]())

# ЭТАП 2: Справка из словаря
HELP = {"/hello": "поздороваться", "/coin": "подбросить монетку"}
for cmd, about in HELP.items():
    print(f"{cmd} — {about}")

# ЭТАП 3: Несколько инструментов у агента
from agent import agent_answer, make_tool


def roll_dice(sides=6):
    return random.randint(1, sides)


TOOLS = [make_tool("coin_flip", "Подбросить монетку: орёл или решка."),
         make_tool("roll_dice", "Бросить кубик. Без числа граней — обычный на 6.",
                   {"sides": {"type": "integer", "description": "Число граней"}})]
FUNCTIONS = {"coin_flip": lambda args: cmd_coin(), "roll_dice": lambda args: roll_dice(args.get("sides", 6))}

# ЭТАП 4: Агент сам выбирает
for question in ["Подбрось монетку", "Брось кубик на 20"]:
    print("Агент:", agent_answer([{"role": "user", "content": question}], TOOLS, FUNCTIONS))
