# Задание 2. Магазин без аварий
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

SHOP = ["мяч", "кубик", "книга"]


def get_item(index):
    try:
        return SHOP[index]
    except IndexError:
        return "Ошибка: нет товара с таким номером"


TOOLS = [make_tool("get_item", "Узнать товар по номеру на полке (нумерация с нуля).",
                   {"index": {"type": "integer", "description": "Номер товара"}}, ["index"])]
FUNCTIONS = {"get_item": lambda args: get_item(args["index"])}
SYSTEM = "Ты продавец. Товары узнавай только инструментом get_item."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
