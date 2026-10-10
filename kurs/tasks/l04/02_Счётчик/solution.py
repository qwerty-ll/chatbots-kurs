# Задание 2. Счётчик сообщений
# Условие — в панели справа. Напиши программу ниже сам.

count = 0
while True:
    text = input("Ты: ")
    if text == "/exit":
        print("Всего сообщений:", count)
        break
    count += 1
    print(f"Сообщение №{count}")
