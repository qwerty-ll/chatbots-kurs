# Задание 2. Калькулятор с операцией
# Условие — в панели справа. Напиши программу ниже сам.

def calc(a, op, b):
    if op == "+":
        return a + b
    elif op == "-":
        return a - b
    elif op == "*":
        return a * b
    elif op == "/":
        return a / b
    return "Неизвестная операция"


a = int(input("Число: "))
op = input("Операция: ").strip()
b = int(input("Число: "))
print("Ответ:", calc(a, op, b))
