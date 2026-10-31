# Задание 10. Болтун: прозвища и счётчик
import random
from ai import ask

NICKS = ["Капитан Код", "Мастер Питона", "Повелитель Циклов"]
count = 0

# В цикле while True:
# text = input("Ты: ").strip()
# 1. Если "/exit" — break
# 2. Если "/nick" — выведи random.choice(NICKS)
# 3. Если "/count" — выведи f"Ты отправил {count} сообщений"
# 4. Иначе: увеличь count += 1, спроси ask(text) и выведи ответ
