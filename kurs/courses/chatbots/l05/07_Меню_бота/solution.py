def tip():
    return "Проверь кавычки."


def fact():
    return "У осьминога три сердца."


command = input("Команда (совет или факт): ")
if command == "совет":
    print(tip())
elif command == "факт":
    print(fact())
else:
    print("Такой команды нет.")
