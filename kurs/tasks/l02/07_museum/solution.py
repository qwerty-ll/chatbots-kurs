age = int(input("Сколько тебе лет? "))
if age < 7 or age > 60:
    print("Вход бесплатный")
elif age >= 7 and age <= 17:
    print("Школьный билет: 100 рублей")
else:
    print("Взрослый билет: 300 рублей")
