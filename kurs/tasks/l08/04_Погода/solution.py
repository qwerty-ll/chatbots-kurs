# Задание 4. Погода в JSON
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json

from agent import agent_answer, make_tool

WEATHER = {"Москва": {"temp": 3, "sky": "облачно"}, "Сочи": {"temp": 15, "sky": "солнечно"}}


def weather(city):
    if city not in WEATHER:
        return json.dumps({"error": "Нет данных"}, ensure_ascii=False)
    data = {"city": city, "temp": WEATHER[city]["temp"], "sky": WEATHER[city]["sky"]}
    return json.dumps(data, ensure_ascii=False)


TOOLS = [make_tool("weather", "Узнать погоду в городе.",
                   {"city": {"type": "string", "description": "Город, например Москва"}}, ["city"])]
FUNCTIONS = {"weather": lambda args: weather(args["city"])}
SYSTEM = "Ты синоптик. Погоду узнавай только инструментом weather."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
