# Тетрадь урока 7. Инструменты с параметрами
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Функция с двумя параметрами
def add(a, b):
    return a + b


print(add(2, 3))

# ЭТАП 2: Калькулятор с операцией
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


print(calc(6, "*", 7), calc(5, "/", 0))

# ЭТАП 3: Описание инструмента с параметрами
from agent import agent_answer, make_tool

TOOLS = [make_tool("calculate", "Точно посчитать выражение a op b.",
                   {"a": {"type": "number", "description": "Первое число"},
                    "op": {"type": "string", "description": "Операция: + - * /"},
                    "b": {"type": "number", "description": "Второе число"}},
                   ["a", "op", "b"])]
FUNCTIONS = {"calculate": lambda args: calc(args["a"], args["op"], args["b"])}

# ЭТАП 4: Агент считает точно
messages = [{"role": "user", "content": "Сколько будет 4817 * 23?"}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
