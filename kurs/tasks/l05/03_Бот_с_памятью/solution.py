# Задание 3. Бот с памятью
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

from ai import chat_text

history = []
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    history.append({"role": "user", "content": text})
    answer = chat_text(history)
    history.append({"role": "assistant", "content": answer})
    print("Бот:", answer)
