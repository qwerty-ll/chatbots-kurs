# Задание 5. Конвертер расстояний
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

UNITS = {"км": 1000, "м": 1, "см": 0.01}


def to_meters(value, unit):
    if unit not in UNITS:
        return "Не знаю такую единицу"
    return f"{value} {unit} = {value * UNITS[unit]} м"


TOOLS = [make_tool("to_meters", "Перевести расстояние в метры.",
                   {"value": {"type": "number", "description": "Число"},
                    "unit": {"type": "string", "description": "Единица: км, м или см"}},
                   ["value", "unit"])]
FUNCTIONS = {"to_meters": lambda args: to_meters(args["value"], args["unit"])}
SYSTEM = "Ты помощник по физике. Для перевода расстояний используй инструмент to_meters."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
