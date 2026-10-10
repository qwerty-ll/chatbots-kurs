# Задание 6. Агент с блокнотом
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json
import os

from agent import agent_answer, make_tool

FILE = "notes.json"


def load():
    if os.path.exists(FILE):
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_note(text):
    notes = load()
    notes.append(text)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False)
    return "Заметка сохранена"


def read_notes():
    notes = load()
    return "; ".join(notes) if notes else "Заметок пока нет"


TOOLS = [make_tool("save_note", "Сохранить заметку пользователя.",
                   {"text": {"type": "string", "description": "Текст заметки"}}, ["text"]),
         make_tool("read_notes", "Показать все сохранённые заметки.")]
FUNCTIONS = {"save_note": lambda args: save_note(args["text"]), "read_notes": lambda args: read_notes()}

messages = [{"role": "system", "content": "Ты помощник с блокнотом. Для заметок используй инструменты."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
