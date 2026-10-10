# Задание 2. Меню персонажей
# Условие — в панели справа. Напиши программу ниже сам.

PERSONAS = {"1": "Пират", "2": "Учитель", "3": "Повар"}


def choose_persona():
    print("1 — Пират")
    print("2 — Учитель")
    print("3 — Повар")
    choice = input("Номер: ").strip()
    return PERSONAS.get(choice, "Пират")


print("Выбран:", choose_persona())
