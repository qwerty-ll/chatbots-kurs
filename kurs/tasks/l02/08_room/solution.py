has_card = False
choice = input("Дверь или шкаф? ").lower().strip()
if choice == "шкаф":
    print("Ты находишь ключ-карту!")
    has_card = True
elif choice == "дверь":
    print("Дверь заперта.")
else:
    print("Время вышло. КОНЕЦ.")
    exit()
answer = input("Открыть дверь? (да/нет) ").lower().strip()
if answer == "да" and has_card:
    print("ПОБЕДА! Дверь открыта.")
elif answer == "да":
    print("Нужна ключ-карта. КОНЕЦ.")
else:
    print("Ты остался в комнате. КОНЕЦ.")
