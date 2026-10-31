name = input("Имя рыцаря: ")
weapon = input("Оружие: ")
if weapon == "меч":
    print(f"{name} обнажает стальной меч и готов к битве!")
elif weapon == "лук":
    print(f"{name} натягивает тетиву лука и целится из засады!")
else:
    print(f"{name} идёт в бой голыми руками!")
