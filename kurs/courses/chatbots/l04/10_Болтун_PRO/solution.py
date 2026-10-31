# Задание 10. Болтун: прозвища и счётчик
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: подключай его строкой from ai import ask

import random

from ai import ask

NICKS = ["Капитан Код", "Мастер Питона", "Повелитель Циклов"]
count = 0
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        print("Пока!")
        break
    elif text == "/nick":
        print(random.choice(NICKS))
    elif text == "/count":
        print(f"Ты отправил {count} сообщений")
    else:
        count += 1
        print(ask(text))
