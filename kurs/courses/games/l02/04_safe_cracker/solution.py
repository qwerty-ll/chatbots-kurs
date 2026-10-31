code = 42
guess = int(input("Введи код: "))
if guess == code:
    print("Сейф открыт! Сокровища ваши!")
elif guess < code:
    print("Код больше! Сигнализация тикает...")
else:
    print("Код меньше! Сигнализация тикает...")
