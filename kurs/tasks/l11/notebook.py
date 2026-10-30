# Тетрадь урока 11. Надёжный агент: ошибки и безопасность
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Безопасное число
def safe_int(text):
    try:
        return int(text)
    except ValueError:
        return None


print(safe_int("12"), safe_int("двенадцать"))

# ЭТАП 2: Инструмент не падает
SHOP = ["мяч", "кубик", "книга"]


def get_item(index):
    try:
        return SHOP[index]
    except IndexError:
        return "Ошибка: нет товара с таким номером"


print(get_item(1), get_item(10))

# ЭТАП 3: Белый список
ALLOWED = ["правила.txt"]


def read_file(name):
    if name not in ALLOWED:
        return "Нет доступа к этому файлу"
    with open(name, encoding="utf-8") as f:
        return f.read()


print(read_file("секрет.txt"))

# ЭТАП 4: Подтверждение человеком
def order_pizza(size):
    answer = input(f"Подтвердить заказ пиццы ({size})? (да/нет) ").strip().lower()
    return "Заказ оформлен" if answer == "да" else "Заказ отменён"


# ЭТАП 5: Журнал
LOG = []


def logged(name, result):
    LOG.append(f"{name} -> {result}")
    return result


print(logged("get_item", get_item(0)), LOG)
