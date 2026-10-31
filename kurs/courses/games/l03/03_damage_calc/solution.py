hp = 30
while hp > 0:
    dmg = int(input("Урон: "))
    hp -= dmg
    if hp > 0:
        print(f"Манекен ранен: осталось {hp} HP")
print("Манекен разбит!")
