# Задание 5. Два кубика
# Условие — в панели справа. Напиши программу ниже сам.

import random

a = random.randint(1, 6)
b = random.randint(1, 6)
print("Кубик 1:", a)
print("Кубик 2:", b)
print("Сумма:", a + b)
if a == b:
    print("Дубль!")
