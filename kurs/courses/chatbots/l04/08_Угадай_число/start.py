# Задание 8. Угадай число
import random

secret = random.randint(1, 20)
tries = 0

# В цикле while True:
# 1. Спроси число: guess = int(input("Твоё число: "))
# 2. Увеличь счётчик попыток: tries += 1
# 3. Сравни с secret:
#    - если guess < secret: выведи "Больше!"
#    - если guess > secret: выведи "Меньше!"
#    - иначе: выведи f"Угадал за {tries} попыток!" и сделай break
