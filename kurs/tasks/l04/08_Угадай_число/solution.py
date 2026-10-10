# Задание 8. Угадай число
# Условие — в панели справа. Напиши программу ниже сам.

import random

secret = random.randint(1, 20)
tries = 0
while True:
    guess = int(input("Твоё число: "))
    tries += 1
    if guess < secret:
        print("Больше!")
    elif guess > secret:
        print("Меньше!")
    else:
        print(f"Угадал за {tries} попыток!")
        break
