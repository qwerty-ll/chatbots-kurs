# Задание 3. Попугай не любит пустоту
# Условие — в панели справа. Напиши программу ниже сам.

while True:
    text = input("Ты: ").strip()
    if text == "":
        continue
    if text == "/exit":
        print("Пока!")
        break
    print(f"Попугай: {text}!")
