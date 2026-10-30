# Тетрадь урока 9. Память агента
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Заметки в списке
notes = []
notes.append("купить хлеб")
notes.append("позвонить бабушке")
for i, note in enumerate(notes, 1):
    print(f"{i}. {note}")

# ЭТАП 2: Только последние три
notes = notes[-3:]

# ЭТАП 3: Сохраняем в файл и читаем обратно
import json

with open("notes.json", "w", encoding="utf-8") as f:
    json.dump(notes, f, ensure_ascii=False)
with open("notes.json", encoding="utf-8") as f:
    print(json.load(f))

# ЭТАП 4: Агент с блокнотом
from agent import agent_answer, make_tool


def add_note(text):
    notes.append(text)
    return f"Запомнил: {text}"


def list_notes():
    return "; ".join(notes) if notes else "Заметок нет"


TOOLS = [make_tool("add_note", "Запомнить заметку.", {"text": {"type": "string", "description": "Текст заметки"}}, ["text"]),
         make_tool("list_notes", "Показать все заметки.")]
FUNCTIONS = {"add_note": lambda args: add_note(args["text"]), "list_notes": lambda args: list_notes()}

# ЭТАП 5: Разговор с короткой памятью
messages = [{"role": "system", "content": "Ты помощник с блокнотом."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    messages = [messages[0]] + messages[1:][-6:]
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
