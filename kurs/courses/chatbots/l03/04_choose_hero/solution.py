from ai import ask

hero = input("Кто будет отвечать: пират, робот или учитель? ").lower().strip()
question = input("Твой вопрос: ")
if hero == "пират":
    role = "Ты весёлый пират."
elif hero == "робот":
    role = "Ты вежливый робот."
elif hero == "учитель":
    role = "Ты добрый учитель."
else:
    role = ""
if role:
    print(ask(question, system=role))
else:
    print("Такого героя я не знаю.")
