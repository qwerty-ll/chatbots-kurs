grid = ["· ● ·", "● ● ●", "· ● ·"]
print("Колония био-точек:")
for row in grid:
    print(row)
total = sum(r.count("●") for r in grid)
print(f"Всего живых клеток: {total}")
