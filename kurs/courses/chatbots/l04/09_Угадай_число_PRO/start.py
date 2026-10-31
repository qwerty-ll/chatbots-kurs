# Задание 9. Угадай число: 5 попыток и защита
import random

secret = random.randint(1, 20)
tries = 0
won = False

# Цикл на 5 попыток: while tries < 5:
# 1. Защити ввод от букв через try: guess = int(input(...)) except ValueError: ... continue
# 2. Увеличивай tries += 1
# 3. Сравнивай с secret и подсказывай "Больше!" или "Меньше!"
# 4. При угадывании: won = True и break
# После цикла, если not won: выведи f"Ты проиграл! Было число {secret}"
