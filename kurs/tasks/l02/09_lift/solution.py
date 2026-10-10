code = input("Код лифта (7 + 8 * 2): ")
card = input("Есть ключ-карта? (да/нет) ").lower().strip()
if code == "23":
    if card == "да":
        print("ПОБЕДА! Лифт едет вверх.")
    else:
        print("Нужна карта. КОНЕЦ.")
else:
    print("Неверный код. КОНЕЦ.")
