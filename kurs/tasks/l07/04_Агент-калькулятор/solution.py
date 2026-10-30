# Задание 4. Агент-калькулятор
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool


def calc(a, op, b):
    if op == "+":
        return a + b
    elif op == "-":
        return a - b
    elif op == "*":
        return a * b
    elif op == "/":
        try:
            return a / b
        except ZeroDivisionError:
            return "На ноль делить нельзя"
    return "Неизвестная операция"


TOOLS = [make_tool("calculate", "Точно посчитать выражение a op b.",
                   {"a": {"type": "number", "description": "Первое число"},
                    "op": {"type": "string", "description": "Операция: + - * /"},
                    "b": {"type": "number", "description": "Второе число"}},
                   ["a", "op", "b"])]
FUNCTIONS = {"calculate": lambda args: calc(args["a"], args["op"], args["b"])}
SYSTEM = "Ты помощник по математике. Для любых вычислений используй инструмент calculate."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
