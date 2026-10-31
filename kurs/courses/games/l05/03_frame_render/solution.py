pos = int(input("Позиция машинки (0-4): "))
lane = "·" * pos + "🏎" + "·" * (4 - pos)
print(f"|{lane}|")
