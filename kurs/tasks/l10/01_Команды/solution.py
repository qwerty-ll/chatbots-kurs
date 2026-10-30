# Задание 1. Команды через словарь
# Условие — в панели справа. Напиши программу ниже сам.

def hello():
    return "Привет!"


def joke():
    return "Почему программисты путают Хэллоуин и Рождество? 31 OCT = 25 DEC"


def help_cmd():
    return "Команды: /hello /joke /help"


COMMANDS = {"/hello": hello, "/joke": joke, "/help": help_cmd}

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    if text in COMMANDS:
        print(COMMANDS[text]())
    else:
        print("Не знаю такой команды")
