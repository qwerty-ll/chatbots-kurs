# Задание 9. Мастер подземелий: кубик
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask

import random

from ai import ask

hp = 10
while True:
    move = input("Твой ход (атака / выход): ").strip().lower()
    if move == "выход":
        break
    if move != "атака":
        continue
    roll = random.randint(1, 20)
    print("Кубик:", roll)
    if roll >= 10:
        hp -= 5
        result = "Попал"
    else:
        result = "Промах"
    print(result + "!")
    print(ask(f"Ты мастер подземелий. Игрок атаковал монстра: {result}. Опиши удар одним предложением."))
    if hp <= 0:
        print("Монстр повержен! Победа!")
        break
