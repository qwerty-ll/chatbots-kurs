# Задание 6. Обрезка истории: trim
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

from ai import chat_text


def trim(history):
    if len(history) > 5:
        return history[:1] + history[-4:]
    return history


history = [{"role": "system", "content": "Ты весёлый пират. Отвечай коротко."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    history = trim(history)
    history.append({"role": "user", "content": text})
    answer = chat_text(history)
    history.append({"role": "assistant", "content": answer})
    print("Пират:", answer)
