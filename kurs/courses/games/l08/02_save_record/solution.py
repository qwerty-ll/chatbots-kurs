name = input("Имя: ")
score = input("Очки: ")
with open("records.txt", "w") as f:
    f.write(f"{name}: {score}")
print("Рекорд успешно сохранён в records.txt!")
