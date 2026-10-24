# Мои инструменты для бота команды
# Условие — в панели справа. Здесь только ТВОИ инструменты: каждый пишет свой файл, и вы не мешаете друг другу.
# Инструменты товарищей лежат в папке «Команда» (только для чтения). Весь бот команды — файл Наш_бот.py.
# Замени все ___ на своё.

import random
from datetime import datetime

from agent import make_tool


# ТВОЁ: первый инструмент — без параметров (совет дня, случайный факт, комплимент…)
def ___():
    return ___


# ТВОЁ: второй инструмент — с параметром (рецепт по продукту, перевод слова, оценка ответа…)
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


# ▶ Запусти этот файл — с тобой поговорит агент только с ТВОИМИ инструментами.
# Наш_бот.py этот кусок не запускает: он берёт отсюда только TOOLS и FUNCTIONS.
if __name__ == "__main__":
    from agent import agent_answer

    messages = [{"role": "system", "content": "Ты помощник. Если подходит инструмент — используй его."}]
    while True:
        text = input("Ты: ").strip()
        if text == "/exit":
            break
        messages.append({"role": "user", "content": text})
        answer = agent_answer(messages, TOOLS, FUNCTIONS)
        messages.append({"role": "assistant", "content": answer})
        print("Агент:", answer)
