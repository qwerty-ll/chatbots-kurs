# Задание 9. Угадай число: 5 попыток и защита
# Условие — в панели справа. Напиши программу ниже сам.

import random

secret = random.randint(1, 20)
tries = 0
won = False
while tries < 5:
    try:
        guess = int(input("Твоё число: "))
    except ValueError:
        print("Это не число!")
        continue
    tries += 1
    if guess < secret:
        print("Больше!")
    elif guess > secret:
        print("Меньше!")
    else:
        print(f"Угадал за {tries} попыток!")
        won = True
        break
if not won:
    print(f"Ты проиграл! Было число {secret}")
