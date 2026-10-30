# Задание 4. Агент-блокнот
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

NOTES = []


def add_note(text):
    NOTES.append(text)
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
