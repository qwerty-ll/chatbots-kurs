# Задание 6. Агент-справочник о планетах
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json

from agent import agent_answer, make_tool

PLANETS = {
    "Марс": {"radius_km": 3390, "moons": 2},
    "Земля": {"radius_km": 6371, "moons": 1},
    "Юпитер": {"radius_km": 69911, "moons": 95},
}


def planet_info(name):
    if name not in PLANETS:
        return "Нет такой планеты"
    data = {"name": name, "radius_km": PLANETS[name]["radius_km"], "moons": PLANETS[name]["moons"]}
    return json.dumps(data, ensure_ascii=False)


TOOLS = [make_tool("planet_info", "Справка о планете: радиус и число спутников.",
                   {"name": {"type": "string", "description": "Планета по-русски: Марс, Земля, Юпитер"}}, ["name"])]
FUNCTIONS = {"planet_info": lambda args: planet_info(args["name"])}
SYSTEM = "Ты астроном. Факты о планетах бери только из инструмента planet_info."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
