# Мои инструменты для бота команды
# Условие — в панели справа. Здесь только ТВОИ инструменты: каждый пишет свой файл, и вы не мешаете друг другу.
# Инструменты товарищей лежат в папке «Команда» (только для чтения). Весь бот команды — файл Наш_бот.py.
# Замени все ___ на своё.

import random
from datetime import datetime

from agent import make_tool


def tip_of_day():
    return random.choice(["Попробуй новое блюдо на этой неделе.", "Готовь вместе с другом — так веселее."])


def find_recipe(product):
    recipes = {"яйца": "омлет", "картошка": "пюре", "молоко": "блинчики"}
    dish = recipes.get(product.lower().strip(), "суп — его можно сварить почти из всего")
    return f"Из продукта «{product}» можно сделать: {dish}."


TOOLS = [
    make_tool("tip_of_day", "Дать кулинарный совет дня."),
    make_tool("find_recipe", "Подсказать блюдо из продукта, который назвал человек.",
              {"product": {"type": "string", "description": "Продукт, например яйца"}}, ["product"]),
]

FUNCTIONS = {
    "tip_of_day": lambda args: tip_of_day(),
    "find_recipe": lambda args: find_recipe(args["product"]),
}


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
