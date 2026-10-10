hour = int(input("Который час (0-23)? "))
if hour < 12:
    print("Доброе утро!")
elif hour < 18:
    print("Добрый день!")
else:
    print("Добрый вечер!")
