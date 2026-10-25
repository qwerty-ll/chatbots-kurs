# Мои инструменты для бота команды
# Условие — в панели справа. Здесь только ТВОИ инструменты: каждый пишет свой файл, и вы не мешаете друг другу.
# Инструменты товарищей лежат в папке «Команда» (только для чтения). Весь бот команды — файл Наш_бот.py.
# Доделано после занятия: пропуски ___ заполнены, ошибки исправлены (что именно — в ИСПРАВЛЕНИЯ.md).

import random
from datetime import datetime

from agent import make_tool

# ТВОЁ: первый инструмент — без параметров (совет дня, случайный факт, комплимент…)
def compliment():
    return random.choice([
        "Ты сегодня хорошо выглядишь!",
        "У тебя классная улыбка!",
        "С тобой приятно общаться!",
        "Ты умнее, чем думаешь!",
    ])


# ТВОЁ: второй инструмент — с параметром (рецепт по продукту, перевод слова, оценка ответа…)
def support(problem):
    return (f"Я понимаю: «{problem}» — это непросто. Но у тебя всё получится! "
            f"Сделай один маленький шаг сегодня, а я буду за тебя болеть.")


# Описания для нейросети: она читает только их — пиши понятно
TOOLS = [
    make_tool("compliment", "Говорит пользователю добрый комплимент."),
    make_tool("support", "Поддерживает пользователя, когда у него что-то не получается.",
              {"problem": {"type": "string", "description": "Что не получается или что беспокоит"}}, ["problem"]),
]

# Имя инструмента -> какую функцию запустить
FUNCTIONS = {
    "compliment": lambda args: compliment(),
    "support": lambda args: support(args["problem"]),
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
