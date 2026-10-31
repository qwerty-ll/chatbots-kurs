hero_hp = 20
dragon_hp = 30
while hero_hp > 0 and dragon_hp > 0:
    act = input("Твой ход (атака/лечение): ")
    if act == "атака":
        dragon_hp -= 15
        print("Герой нанёс 15 урона дракону!")
    elif act == "лечение":
        hero_hp += 5
        print("Герой выпил зелье и восстановил 5 HP!")
    if dragon_hp > 0:
        hero_hp -= 10
        print("Дракон дышит пламенем: герой теряет 10 HP!")
if dragon_hp <= 0:
    print("Дракон побеждён! Слава герою!")
else:
    print("Герой пал в битве...")
