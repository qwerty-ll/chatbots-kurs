code = 7
guessed = False

# Попытка 1
guess = int(input("Попытка: "))
if guess == code:
    print("Взлом успешен!")
    guessed = True
elif guess < code:
    print("Код больше!")
else:
    print("Код меньше!")

# Попытка 2
if not guessed:
    guess = int(input("Попытка: "))
    if guess == code:
        print("Взлом успешен!")
        guessed = True
    elif guess < code:
        print("Код больше!")
    else:
        print("Код меньше!")

# Попытка 3
if not guessed:
    guess = int(input("Попытка: "))
    if guess == code:
        print("Взлом успешен!")
        guessed = True
    elif guess < code:
        print("Код больше!")
    else:
        print("Код меньше!")

# Проверка сигнализации
if not guessed:
    print("Сигнализация сработала!")
