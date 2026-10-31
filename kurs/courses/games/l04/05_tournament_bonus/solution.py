log = []
while True:
    res = input("Исход раунда: ")
    if res == "стоп":
        break
    log.append(res)
print(f"Всего раундов: {len(log)}")
print(f"Журнал: {log}")
