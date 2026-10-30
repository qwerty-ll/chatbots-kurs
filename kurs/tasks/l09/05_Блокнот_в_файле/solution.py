# Задание 5. Блокнот, который не забывает
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json

from agent import agent_answer, make_tool

try:
    with open("notes.json", encoding="utf-8") as f:
        NOTES = json.load(f)
except FileNotFoundError:
    NOTES = []


def add_note(text):
    NOTES.append(text)
    with open("notes.json", "w", encoding="utf-8") as f:
        json.dump(NOTES, f, ensure_ascii=False)
    return f"Запомнил: {text}"


def list_notes():
    if not NOTES:
        return "Заметок нет"
    return "; ".join(NOTES)


TOOLS = [make_tool("add_note", "Запомнить заметку.", {"text": {"type": "string", "description": "Текст заметки"}}, ["text"]),
         make_tool("list_notes", "Показать все заметки.")]
FUNCTIONS = {"add_note": lambda args: add_note(args["text"]), "list_notes": lambda args: list_notes()}
SYSTEM = "Ты помощник с блокнотом. Заметки сохраняй и показывай только инструментами."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
