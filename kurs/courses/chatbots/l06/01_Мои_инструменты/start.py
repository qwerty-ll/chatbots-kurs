# Заполни две пустые строки: название и текст карточки.
from agent import preview_card

CARD_TITLE = ""


def get_card():
    return ""


# Бонус после /demo. Измени фразу, которую выдаёт подсказка.
def hint():
    return "Проверь, что лежит у окна."


EXTRA_TOOLS = {
    # Чтобы включить подсказку, убери знак # в начале следующей строки.
    # "Подсказка": (hint, "Подсказать ход"),
}


if __name__ == "__main__":
    preview_card(CARD_TITLE, get_card)
