for pct in [25, 50, 75, 100]:
    k = pct // 10
    bar = "=" * k + " " * (10 - k)
    print(f"Загрузка: [{bar}] {pct}%")
