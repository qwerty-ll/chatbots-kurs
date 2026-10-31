# Задание 7. Бот-болтун с командами
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: подключай его строкой from ai import ask

import random

from ai import ask

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        print("Пока!")
        break
    elif text == "/help":
        print("Команды: /help, /coin, /exit. Остальное — нейросети.")
    elif text == "/coin":
        print(random.choice(["Орёл", "Решка"]))
    else:
        print(ask(text))
