code = 7
guessed = False
for i in range(3):
    guess = int(input("Попытка: "))
    if guess == code:
        print("Взлом успешен!")
        guessed = True
        break
    elif guess < code:
        print("Код больше!")
    else:
        print("Код меньше!")
if not guessed:
    print("Сигнализация сработала!")
