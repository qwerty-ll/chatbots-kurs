# Задание 7. Прототип моего проекта
# Условие — в панели справа. Замени все ___ на своё — получится первый агент с твоей идеей.
# Рядом лежат ai.py и agent.py.

import random

from agent import agent_answer, make_tool

# ТВОЁ: кто твой бот и как он говорит
PERSONA = ("___ "
           "Говоришь по-русски, коротко. Если подходит инструмент — используй его, а не выдумывай.")


# ТВОЁ: первый инструмент — без параметров (совет дня, случайный факт, комплимент…)
def ___():
    return ___


# ТВОЁ: второй инструмент — с параметром (рецепт по продукту, перевод слова, совет по теме…)
def ___(___):
    return ___


# Описания для нейросети: она читает только их — пиши понятно
TOOLS = [
    make_tool("___", "___"),
    make_tool("___", "___",
              {"___": {"type": "string", "description": "___"}}, ["___"]),
]

# Имя инструмента -> какую функцию запустить
FUNCTIONS = {
    "___": lambda args: ___(),
    "___": lambda args: ___(args["___"]),
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
