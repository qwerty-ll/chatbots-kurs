# Задание 6. Итоговый проект: мой агент
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json
import random

from agent import agent_answer, make_tool

AGENT = {"name": "Бобо", "role": "помощник по уходу за питомцами", "rules": ["отвечай коротко", "советы бери из инструментов"]}

try:
    with open("pets.json", encoding="utf-8") as f:
        PETS = json.load(f)
except FileNotFoundError:
    PETS = []

FOOD = {"кошка": "2 раза в день", "собака": "2 раза в день", "попугай": "зерно каждый день"}


def make_system(agent):
    return f"Ты {agent['name']}, {agent['role']}. Правила: " + "; ".join(agent["rules"]) + "."


def add_pet(name, kind):
    PETS.append({"name": name, "kind": kind})
    with open("pets.json", "w", encoding="utf-8") as f:
        json.dump(PETS, f, ensure_ascii=False)
    return f"Запомнил питомца: {name} ({kind})"


def feeding(kind):
    return FOOD.get(kind, "Про такого питомца не знаю")


def pet_tip():
    return random.choice(["Гуляй с собакой дважды в день.", "Меняй воду каждый день.", "Хвали питомца за хорошее поведение."])


TOOLS = [make_tool("add_pet", "Запомнить питомца.",
                   {"name": {"type": "string", "description": "Кличка"},
                    "kind": {"type": "string", "description": "Кто это: кошка, собака, попугай"}}, ["name", "kind"]),
         make_tool("feeding", "Как часто кормить питомца.",
                   {"kind": {"type": "string", "description": "Вид питомца"}}, ["kind"]),
         make_tool("pet_tip", "Случайный совет по уходу.")]
FUNCTIONS = {"add_pet": lambda args: add_pet(args["name"], args["kind"]),
             "feeding": lambda args: feeding(args["kind"]),
             "pet_tip": lambda args: pet_tip()}

messages = [{"role": "system", "content": make_system(AGENT)}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    messages = [messages[0]] + messages[1:][-6:]
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
