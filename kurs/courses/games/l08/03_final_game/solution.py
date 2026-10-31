name = input("Введи имя героя: ")
print(f"Привет, {name}! Добро пожаловать на Финальную Арену!")
lvl = input("Выбери сложность (1 - Легко, 2 - Хардкор): ")
if lvl == "1":
    score = 100
    print("Уровень пройден! Набрано очков: 100")
else:
    score = 250
    print("Хардкор покорён! Набрано очков: 250")
with open("highscores.txt", "w") as f:
    f.write(f"{name} - {score}")
print("Результат занесён в Зал Славы (highscores.txt)!")
