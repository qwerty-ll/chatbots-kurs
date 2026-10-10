from ai import ask

question = input("Вопрос: ")
q = question.lower()
if "пароль" in q or "телефон" in q or "адрес" in q:
    print("Это личное! Такое нейросети не отправляю.")
else:
    print(ask(question))
