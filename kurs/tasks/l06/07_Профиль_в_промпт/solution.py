# Задание 7. Профиль → промпт
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

from ai import ask


def build_system_prompt(profile):
    facts = "; ".join(f"{key}: {value}" for key, value in profile.items())
    return f"Ты дружелюбный бот. Что ты знаешь о собеседнике: {facts}."


profile = {"имя": input("Имя: ").strip(), "еда": input("Любимая еда: ").strip()}
question = input("Вопрос: ")
print(ask(question, system=build_system_prompt(profile)))
