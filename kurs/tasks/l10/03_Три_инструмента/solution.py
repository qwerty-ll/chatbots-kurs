# Задание 3. Агент с тремя инструментами
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import random

from agent import agent_answer, make_tool


def coin_flip():
    return random.choice(["Орёл", "Решка"])


def get_joke():
    return random.choice(["Кот учит Python, потому что любит ловить баги.",
                          "Программист ушёл в магазин и не вернулся: на полке было написано «бесконечный цикл скидок»."])


def get_fact():
    return random.choice(["У осьминога три сердца.", "Мёд не портится тысячи лет.", "Улитка может спать три года."])


TOOLS = [make_tool("coin_flip", "Подбросить монетку, когда просят орёл или решку."),
         make_tool("get_joke", "Рассказать шутку, когда просят посмешить."),
         make_tool("get_fact", "Сказать интересный факт, когда просят факт.")]
FUNCTIONS = {"coin_flip": lambda args: coin_flip(), "get_joke": lambda args: get_joke(), "get_fact": lambda args: get_fact()}
SYSTEM = "Ты весёлый помощник. Монетку, шутки и факты бери только из инструментов."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
