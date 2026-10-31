# Тетрадь урока 4. Бот, который не уходит
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Цикл while и выход по команде
while True:
    text = input("Ты: ")
    if text == "/exit":
        print("Пока!")
        break
    print("Эхо:", text)

# ЭТАП 2: Список и случайность
import random

JOKES = ["Шутка про Python", "Шутка про циклы", "Шутка про списки"]
print(random.choice(JOKES))
print("Кубик:", random.randint(1, 6))

# ЭТАП 3: Страховка try / except
try:
    a = int(input("Первое число: "))
    b = int(input("Второе число: "))
    print("Сумма:", a + b)
except ValueError:
    print("Это не число!")

# ЭТАП 4: Бот-болтун: команды + нейросеть
from ai import ask

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        print("Пока!")
        break
    elif text == "/joke":
        print(random.choice(JOKES))
    elif text == "/dice":
        print("Выпало", random.randint(1, 6))
    else:
        print(ask(text, system="Ты весёлый бот-болтун. Отвечай коротко."))
