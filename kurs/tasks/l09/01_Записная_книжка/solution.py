# Задание 1. Записная книжка
# Условие — в панели справа. Напиши программу ниже сам.

notes = []
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    elif text == "/list":
        for i, note in enumerate(notes, 1):
            print(f"{i}. {note}")
    else:
        notes.append(text)
        print("Записал!")
