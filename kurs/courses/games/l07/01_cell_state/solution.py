state = input("Статус (жива/мертва): ")
n = int(input("Соседей (0-8): "))
if state == "жива" and (n == 2 or n == 3):
    print("● Жива")
elif state == "мертва" and n == 3:
    print("● Ожила")
else:
    print("· Мертва")
