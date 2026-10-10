from ai import ask

secret = input("Загадай слово: ").lower().strip()
riddle = ask(f"Придумай короткую загадку про «{secret}». Само слово не называй.")
print(riddle)
guess = input("Отгадка: ").lower().strip()
if guess == secret:
    print("Верно!")
else:
    print("Не угадал! Это был", secret)
