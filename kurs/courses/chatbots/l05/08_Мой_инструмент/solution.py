def answer():
    return "Раздели большую задачу на две маленькие."


TOOLS = {"совет": answer}
command = input("Команда: ")
if command in TOOLS:
    tool = TOOLS[command]
    print("Бот:", tool())
else:
    print("Попробуй команду «совет».")
