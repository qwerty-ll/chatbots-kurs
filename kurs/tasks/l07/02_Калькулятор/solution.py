# Задание 2. Инструмент-калькулятор без eval
# Условие — в панели справа. Напиши программу ниже сам.

def calculate(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            return "На ноль делить нельзя"
        return a / b
    return "Не знаю такого действия"


a = int(input("a: "))
op = input("Действие: ").strip()
b = int(input("b: "))
print("Ответ:", calculate(a, op, b))
