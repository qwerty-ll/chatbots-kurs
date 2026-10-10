# Задание 7. Команда /history
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

from ai import chat_text

history = [{"role": "system", "content": "Ты дружелюбный бот. Отвечай коротко."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    if text == "/history":
        for message in history:
            if message["role"] == "user":
                print("Ты:", message["content"])
            elif message["role"] == "assistant":
                print("Бот:", message["content"])
        continue
    history.append({"role": "user", "content": text})
    answer = chat_text(history)
    history.append({"role": "assistant", "content": answer})
    print("Бот:", answer)
