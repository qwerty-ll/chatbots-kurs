# ЭТАП 1: Функция возвращает текст
def get_card():
    return "Найди три предмета на букву К."


print(get_card())

# ЭТАП 2: Случайная карточка
import random


def draw_card():
    return random.choice(["Назови слово на букву К.", "Придумай имя роботу."])


print(draw_card())
