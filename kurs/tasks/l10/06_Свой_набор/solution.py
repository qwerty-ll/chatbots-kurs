# Задание 6. Свой набор инструментов
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool

CALORIES = {"бег": 10, "плавание": 8, "велосипед": 7}


def workout():
    return random.choice(["20 приседаний и планка 1 минута", "3 круга по 10 отжиманий", "15 минут бега"])


def burn(sport, minutes):
    if sport not in CALORIES:
        return "Не знаю такой вид спорта"
    return f"{sport}: {CALORIES[sport] * minutes} ккал за {minutes} мин"


def water(weight):
    return f"Пей около {weight * 30} мл воды в день"


TOOLS = [make_tool("workout", "Посоветовать тренировку на сегодня."),
         make_tool("burn", "Посчитать, сколько калорий сжигает спорт.",
                   {"sport": {"type": "string", "description": "бег, плавание или велосипед"},
                    "minutes": {"type": "integer", "description": "Сколько минут"}}, ["sport", "minutes"]),
         make_tool("water", "Сколько воды пить в день.",
                   {"weight": {"type": "integer", "description": "Вес в кг"}}, ["weight"])]
FUNCTIONS = {"workout": lambda args: workout(),
             "burn": lambda args: burn(args["sport"], args["minutes"]),
             "water": lambda args: water(args["weight"])}
SYSTEM = "Ты спортивный тренер. Советы и расчёты бери из инструментов."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
