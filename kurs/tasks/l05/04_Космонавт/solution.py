# Задание 4. Персонаж-космонавт
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

from ai import chat_text

SYSTEM = "Ты космонавт на орбите. Говоришь восторженно, отвечаешь по-русски, до 3 предложений."
history = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    history.append({"role": "user", "content": text})
    answer = chat_text(history)
    history.append({"role": "assistant", "content": answer})
    print("Космонавт:", answer)
