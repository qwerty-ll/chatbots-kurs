# Задание 10. Мастер подземелий: УРОН и НАЙДЕНО
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask

from ai import ask

hp = 10
inventory = []
answer = ask("Придумай событие в подземелье. В конце напиши УРОН=число или НАЙДЕНО=предмет.")
print(answer)
for word in answer.split():
    if word.startswith("УРОН="):
        hp -= int(word.split("=")[1])
    elif word.startswith("НАЙДЕНО="):
        inventory.append(word.split("=")[1])
print("Здоровье:", hp)
if inventory:
    print("Инвентарь:", ", ".join(inventory))
else:
    print("Инвентарь: пусто")
