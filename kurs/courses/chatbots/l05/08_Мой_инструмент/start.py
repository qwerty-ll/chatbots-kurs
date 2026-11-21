def answer():
    return ___


TOOLS = {"совет": ___}
command = input("Команда: ")
if command in TOOLS:
    tool = TOOLS[command]
    print("Бот:", tool())
else:
    print("Попробуй команду «совет».")
