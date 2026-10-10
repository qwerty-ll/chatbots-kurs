# Тетрадь урока 5. Память и характер
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Функция
def greet(name):
    return f"Привет, {name}!"


print(greet("Аня"))

# ЭТАП 2: История переписки
from ai import chat_text

history = [{"role": "system", "content": "Ты весёлый пират. Отвечай до 3 предложений."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    history.append({"role": "user", "content": text})
    answer = chat_text(history)
    history.append({"role": "assistant", "content": answer})
    print("Бот:", answer)

# ЭТАП 3: Команда /reset и обрезка истории
def trim(history):
    if len(history) > 21:
        return history[:1] + history[-20:]
    return history

# в цикле:
#     if text == "/reset":
#         history = history[:1]
#         continue
#     history = trim(history)
