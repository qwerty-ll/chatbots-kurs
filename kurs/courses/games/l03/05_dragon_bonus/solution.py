hp = int(input("HP героя (от 0 до 10): "))
bar = "■" * hp + "□" * (10 - hp)
print(f"HP: [{bar}] {hp}/10")
