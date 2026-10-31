x = 0
y = 0
while not (x == 2 and y == 2):
    cmd = input("Куда идти: ")
    if cmd == "w":
        y -= 1
    elif cmd == "s":
        y += 1
    elif cmd == "a":
        x -= 1
    elif cmd == "d":
        x += 1
    print(f"Герой на позиции: ({x}, {y})")
print("Победа! Вы выбрались из подземелья!")
