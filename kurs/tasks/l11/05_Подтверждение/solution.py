# Задание 5. Спроси человека
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool


def order_pizza(size):
    answer = input("Подтвердить заказ? (да/нет) ").strip().lower()
    if answer == "да":
        return f"Заказ оформлен: пицца {size}"
    return "Заказ отменён"


TOOLS = [make_tool("order_pizza", "Заказать пиццу (человек подтвердит заказ).",
                   {"size": {"type": "string", "description": "Размер: маленькая, средняя, большая"}}, ["size"])]
FUNCTIONS = {"order_pizza": lambda args: order_pizza(args["size"])}
SYSTEM = "Ты помощник пиццерии. Заказы оформляй только инструментом order_pizza."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
