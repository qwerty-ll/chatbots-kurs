a = input("Игрок 1 (камень/ножницы/бумага): ").lower().strip()
b = input("Игрок 2 (камень/ножницы/бумага): ").lower().strip()
bad_a = a != "камень" and a != "ножницы" and a != "бумага"
bad_b = b != "камень" and b != "ножницы" and b != "бумага"
if bad_a or bad_b:
    print("Не понял ход")
elif a == b:
    print("Ничья!")
elif (a == "камень" and b == "ножницы") or (a == "ножницы" and b == "бумага") or (a == "бумага" and b == "камень"):
    print("Победил игрок 1")
else:
    print("Победил игрок 2")
