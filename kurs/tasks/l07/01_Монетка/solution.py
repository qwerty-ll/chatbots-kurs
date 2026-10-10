# Задание 1. Инструмент-монетка
# Условие — в панели справа. Напиши программу ниже сам.

import random


def coin_flip():
    return random.choice(["Орёл", "Решка"])


print("Монетка:", coin_flip())
