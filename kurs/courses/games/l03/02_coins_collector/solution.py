coins = 0
while True:
    cmd = input("Действие: ")
    if cmd == "монета":
        coins += 1
        print("Плюс монета!")
    elif cmd == "стоп":
        break
print(f"Собрано монет: {coins}")
