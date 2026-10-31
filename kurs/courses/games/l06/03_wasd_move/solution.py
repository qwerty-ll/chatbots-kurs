x = 2
y = 2
cmd = input("Ход: ")
if cmd == "w":
    y -= 1
elif cmd == "s":
    y += 1
elif cmd == "a":
    x -= 1
elif cmd == "d":
    x += 1
print(f"Координаты: ({x}, {y})")
