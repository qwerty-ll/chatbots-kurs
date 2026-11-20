"""Бродилка команды. Запуск: python3 01_Бродилка.py."""
import json
from pathlib import Path

LEVEL = [
    "....",
    ".##K",
    "...E",
]
MOVES = {"w": (-1, 0), "a": (0, -1), "s": (1, 0), "d": (0, 1)}
MENU = {"title": "Бродилка", "start": "Играть", "rules": "Правила",
        "exit": "Выход", "intro": "Найди ключ и доберись до выхода."}


def load_menu():
    file = Path(__file__).with_name("studio_menu.json")
    try:
        custom = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MENU
    if not isinstance(custom, dict):
        return MENU
    return {key: custom.get(key) if isinstance(custom.get(key), str) else value
            for key, value in MENU.items()}


def draw(level, row, col, has_key):
    for y, line in enumerate(level):
        if has_key:
            line = line.replace("K", ".")
        if y == row:
            line = line[:col] + "@" + line[col + 1:]
        print(line)


def play(level):
    row, col = 0, 0
    has_key = False
    print("@ — игрок, # — стена, K — ключ, E — выход. w/a/s/d — ход, q — выход.")
    while True:
        draw(level, row, col, has_key)
        try:
            cmd = input("Ход: ").strip().lower()
        except EOFError:
            cmd = "q"
        if cmd == "q":
            print("Игра завершена.")
            break
        if cmd not in MOVES:
            print("Неизвестная команда.")
            continue

        dr, dc = MOVES[cmd]
        next_row, next_col = row + dr, col + dc
        # Шаг 1. Проверь обе границы до чтения клетки.
        # Шаг 2. Проверь стену и закрытый выход. В этих случаях ход отменяется.
        # Шаг 3. Обнови координаты, подбери ключ или объяви победу.
        print("Здесь будет обработка хода.")


def main():
    menu = load_menu()
    while True:
        print(f"=== {menu['title']} ===")
        print(f"1. {menu['start']} | 2. {menu['rules']} | 3. {menu['exit']}")
        try:
            choice = input("Выбор: ").strip()
        except EOFError:
            choice = "3"
        if choice == "1":
            play(LEVEL)
            return
        if choice == "2":
            print(menu["intro"])
            print("Управление: w/a/s/d, q — закончить игру.")
        elif choice == "3":
            print("Игра завершена.")
            return
        else:
            print("Выбери 1, 2 или 3.")


if __name__ == "__main__":
    main()
