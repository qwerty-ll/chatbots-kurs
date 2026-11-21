# Заполни две пустые строки: название и текст карточки.
from agent import preview_card

CARD_TITLE = "Быстрая миссия"


def get_card():
    return "Найди три предмета на букву К."


if __name__ == "__main__":
    preview_card(CARD_TITLE, get_card)
