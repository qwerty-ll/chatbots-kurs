from ai import ask

question = input("Вопрос: ")
print("Строго:", ask(question, temperature=0))
print("Творчески:", ask(question, temperature=1))
