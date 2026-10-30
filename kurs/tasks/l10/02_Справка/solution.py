# Задание 2. Справка из словаря
# Условие — в панели справа. Напиши программу ниже сам.

HELP = {"/hello": "поздороваться", "/joke": "рассказать шутку", "/coin": "подбросить монетку"}

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    elif text == "/help":
        for cmd, about in HELP.items():
            print(f"{cmd} — {about}")
    elif text in HELP:
        print("Выполняю:", HELP[text])
    else:
        print("Нет такой команды. Напиши /help")
