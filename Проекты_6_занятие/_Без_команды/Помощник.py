# Мои инструменты для бота команды
# Условие — в панели справа. Здесь только ТВОИ инструменты: каждый пишет свой файл, и вы не мешаете друг другу.
# Инструменты товарищей лежат в папке «Команда» (только для чтения). Весь бот команды — файл Наш_бот.py.
# Доделано после занятия: пропуски ___ заполнены, ошибки исправлены (что именно — в ИСПРАВЛЕНИЯ.md).

import random
from datetime import datetime

from agent import make_tool

def tip_of_day():
    tips = [
        "Попробуй приготовить новое блюдо на этой неделе",
        "Пей достаточно чистой воды в течение дня",
        "Готовь вместе с другом — так веселее",
    ]
    return random.choice(tips)


def find_recipes(product):
    recipes = {
        "яйца": "сытный омлет с сыром и зеленью",
        "картошка": "вкусное и нежное картофельное пюре",
        "молоко": "тонкие румяные блинчики",
    }
    dish = recipes.get(product.lower().strip(), "густой суп — его можно сварить почти из любых ингредиентов")
    return f"Из продукта «{product}» вы можете приготовить: {dish}"


TOOLS = [
    make_tool("tip_of_day", "Дать кулинарный совет дня."),
    make_tool("find_recipes", "Подсказать блюдо или рецепт по продукту, который назвал человек.",
              {"product": {"type": "string", "description": "Продукт, например яйца, молоко, сыр"}}, ["product"]),
]

FUNCTIONS = {
    "tip_of_day": lambda args: tip_of_day(),
    "find_recipes": lambda args: find_recipes(args["product"]),
}

# ▶ Запусти этот файл — с тобой поговорит агент только с ТВОИМИ инструментами.
# Наш_бот.py этот кусок не запускает: он берёт отсюда только TOOLS и FUNCTIONS.
if __name__ == "__main__":
    from agent import agent_answer

    messages = [{"role": "system", "content": "Ты бот-повар, тебя зовут Шахидик. Говоришь как весёлый повар, отвечаешь коротко и с шутками про еду. Если подходит инструмент — используй его."}]
    while True:
        text = input("Ты: ").strip()
        if text == "/exit":
            break
        messages.append({"role": "user", "content": text})
        answer = agent_answer(messages, TOOLS, FUNCTIONS)
        messages.append({"role": "assistant", "content": answer})
        print("Агент:", answer)
