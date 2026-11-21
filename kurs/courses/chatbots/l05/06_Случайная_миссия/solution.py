import random


def mission():
    missions = ["Найди круг.", "Сосчитай окна."]
    return random.choice(missions)


print("Миссия:", mission())
