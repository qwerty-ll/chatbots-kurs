# Задание 3. Команды /remember и /profile
# Условие — в панели справа. Напиши программу ниже сам.

profile = {}
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    elif text.startswith("/remember "):
        key, value = text[10:].split("=", 1)
        profile[key.strip()] = value.strip()
        print(f"Запомнил: {key.strip()} — {value.strip()}")
    elif text == "/profile":
        for key, value in profile.items():
            print(f"{key}: {value}")
