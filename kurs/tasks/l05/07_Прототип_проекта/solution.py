# Задание 7. Прототип моего проекта
# Условие — в панели справа. Замени все ___ на своё — получится первый агент с твоей идеей.
# Рядом лежат ai.py и agent.py.

import random

from agent import agent_answer, make_tool

PERSONA = ("Ты Робик — дружелюбный робот-помощник по учёбе. "
           "Говоришь по-русски, коротко. Если подходит инструмент — используй его, а не выдумывай.")


def compliment():
    return random.choice(["Ты отлично справляешься!", "Твой код становится лучше каждый день!"])


def advice(topic):
    return f"Совет по теме «{topic}»: разбей задачу на маленькие шаги и начни с самого простого."


TOOLS = [
    make_tool("compliment", "Сказать пользователю случайный комплимент."),
    make_tool("advice", "Дать короткий совет по теме, которую назвал пользователь.",
              {"topic": {"type": "string", "description": "Тема совета"}}, ["topic"]),
]

FUNCTIONS = {
    "compliment": lambda args: compliment(),
    "advice": lambda args: advice(args["topic"]),
}

messages = [{"role": "system", "content": PERSONA}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
