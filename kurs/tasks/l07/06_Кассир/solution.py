# Задание 6. Агент-кассир
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

PRICES = {"пицца": 450, "сок": 120, "булочка": 60}


def total(item, count):
    if item not in PRICES:
        return "Такого нет в меню"
    return f"{count} × {item} = {PRICES[item] * count} ₽"


TOOLS = [make_tool("total", "Посчитать стоимость заказа из меню.",
                   {"item": {"type": "string", "description": "Название из меню: пицца, сок, булочка"},
                    "count": {"type": "integer", "description": "Сколько штук"}},
                   ["item", "count"])]
FUNCTIONS = {"total": lambda args: total(args["item"], args["count"])}
SYSTEM = "Ты кассир кафе. Цены считай только инструментом total."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
