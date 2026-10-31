code = 7

# Попытка 1
guess = int(input("Попытка: "))
if guess == code:
    print("Взлом успешен!")
else:
    if guess < code:
        print("Код больше!")
    else:
        print("Код меньше!")

    # Попытка 2
    guess = int(input("Попытка: "))
    if guess == code:
        print("Взлом успешен!")
    else:
        if guess < code:
            print("Код больше!")
        else:
            print("Код меньше!")

        # Попытка 3
        guess = int(input("Попытка: "))
        if guess == code:
            print("Взлом успешен!")
        else:
            if guess < code:
                print("Код больше!")
            else:
                print("Код меньше!")
            print("Сигнализация сработала!")
