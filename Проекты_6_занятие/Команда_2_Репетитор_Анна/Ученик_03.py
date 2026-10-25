# Мои инструменты для бота команды
# Условие — в панели справа. Здесь только ТВОИ инструменты: каждый пишет свой файл, и вы не мешаете друг другу.
# Инструменты товарищей лежат в папке «Команда» (только для чтения). Весь бот команды — файл Наш_бот.py.
# Доделано после занятия: пропуски ___ заполнены, ошибки исправлены (что именно — в ИСПРАВЛЕНИЯ.md).

import random
from datetime import datetime

from agent import make_tool

# ТВОЁ: первый инструмент — без параметров (совет дня, случайный факт, комплимент…)
def study_hack():
    tips = [
        "Сделай перерыв на 5 минут и попей воды — мозг сразу заработает быстрее!",
        "Разбей сложную задачу на три простых шага и начни с самого лёгкого!",
        "Убери телефон в другую комнату на 20 минут, и домашка решится сама собой!",
        "Съешь кусочек шоколада для бодрости и повтори правило вслух перед зеркалом!",
    ]
    return random.choice(tips)


# ТВОЁ: второй инструмент — с параметром (рецепт по продукту, перевод слова, оценка ответа…)
def translate(topik):
    translations = {
        "привет": "hello",
        "спасибо": "thank you",
        "до свидания": "goodbye",
        "пожалуйста": "please",
        "школа": "school",
        "друг": "friend",
        "кошка": "cat",
        "собака": "dog",
    }
    return translations.get(topik.lower().strip(), f"Я не знаю перевод слова «{topik}»")


# Описания для нейросети: она читает только их — пиши понятно
TOOLS = [
    make_tool("study_hack", "Возвращает короткий весёлый совет для продуктивной и лёгкой учёбы."),
    make_tool("translate", "Переводит слово или фразу с русского на английский.",
              {"topik": {"type": "string", "description": "Слово или фраза на русском"}}, ["topik"]),
]

# Имя инструмента -> какую функцию запустить
FUNCTIONS = {
    "study_hack": lambda args: study_hack(),
    "translate": lambda args: translate(args["topik"]),
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
