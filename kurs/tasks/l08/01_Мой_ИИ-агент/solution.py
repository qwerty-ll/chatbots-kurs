# Задание 1. Мой ИИ-агент (проект)
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py. Замени все ___ на своё — так получится твой агент.

import json
import os
import random
from datetime import datetime

from agent import agent_answer, make_tool

MEMORY_FILE = "project_memory.json"
MAX_HISTORY = 20

BOT_NAME = "Робик"
PERSONA = ("Ты Робик — дружелюбный робот-помощник кружка по программированию. Говоришь по-русски, "
           "коротко и с юмором. Если нужны время, кубик или твои особые умения — используй инструменты, а не выдумывай.")


# ----------------------------- ИНСТРУМЕНТЫ ----------------------------------
def get_time():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def roll_dice(sides=6):
    return random.randint(1, int(sides))


def compliment():
    return random.choice(["Ты отлично справляешься!", "Твой код становится лучше каждый день!"])


def advice(topic):
    return f"Совет по теме «{topic}»: разбей задачу на маленькие шаги и начни с самого простого."


TOOL_FUNCTIONS = {
    "get_time": lambda args: get_time(),
    "roll_dice": lambda args: roll_dice(args.get("sides", 6)),
    "compliment": lambda args: compliment(),
    "advice": lambda args: advice(args["topic"]),
}

TOOLS = [
    make_tool("get_time", "Узнать текущие дату и время."),
    make_tool("roll_dice", "Бросить игральный кубик.",
              {"sides": {"type": "integer", "description": "Число граней, по умолчанию 6"}}),
    make_tool("compliment", "Сказать пользователю случайный комплимент."),
    make_tool("advice", "Дать короткий совет по теме, которую назвал пользователь.",
              {"topic": {"type": "string", "description": "Тема совета"}}, ["topic"]),
]


# ----------------------------- ПАМЯТЬ ---------------------------------------
def load_history():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    # в файл пишем только реплики человека и бота, служебные сообщения инструментов не нужны
    clean = [m for m in history if m["role"] in ("user", "assistant") and m.get("content")]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)


def main():
    history = load_history()
    print(f"{BOT_NAME} на связи! /reset — забыть разговор, /exit — выйти.")
    if history:
        print(f"(помню наш прошлый разговор: {len(history)} реплик)")
    while True:
        text = input("Ты: ").strip()
        if text.lower() == "/exit":
            break
        if text.lower() == "/reset":
            history = []
            save_history(history)
            print(f"{BOT_NAME}: всё забыл!")
            continue
        if not text:
            continue
        messages = [{"role": "system", "content": PERSONA}] + history
        messages.append({"role": "user", "content": text})
        answer = agent_answer(messages, TOOLS, TOOL_FUNCTIONS)
        print(f"{BOT_NAME}:", answer)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": answer})
        history = history[-MAX_HISTORY:]
        save_history(history)


main()
