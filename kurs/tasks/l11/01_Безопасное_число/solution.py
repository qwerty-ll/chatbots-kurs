# Задание 1. Безопасное число
# Условие — в панели справа. Напиши программу ниже сам.

def safe_int(text):
    try:
        return int(text)
    except ValueError:
        return None


age = safe_int(input("Сколько тебе лет? "))
if age is None:
    print("Нужно число")
else:
    print(f"Через год тебе будет {age + 1}")
