pos = 2
score = 0
while True:
    cmd = input("Руль: ")
    if cmd == "стоп":
        break
    if cmd == "a" and pos > 0:
        pos -= 1
    elif cmd == "d" and pos < 4:
        pos += 1
    score += 10
    lane = "·" * pos + "🏎" + "·" * (4 - pos)
    print(f"|{lane}| Очки: {score}")
print(f"Гонка окончена! Финальный счёт: {score}")
