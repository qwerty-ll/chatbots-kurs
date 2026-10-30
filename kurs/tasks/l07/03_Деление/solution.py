# Задание 3. Деление без аварий
# Условие — в панели справа. Напиши программу ниже сам.

def divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return "На ноль делить нельзя"


a = int(input("Делимое: "))
b = int(input("Делитель: "))
print("Результат:", divide(a, b))
