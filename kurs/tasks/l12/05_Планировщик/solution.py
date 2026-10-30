# Задание 5. Агент-планировщик
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json

from agent import agent_answer, make_tool

try:
    with open("tasks.json", encoding="utf-8") as f:
        TASKS = json.load(f)
except FileNotFoundError:
    TASKS = []


def add_task(text, priority):
    TASKS.append({"text": text, "priority": priority})
    with open("tasks.json", "w", encoding="utf-8") as f:
        json.dump(TASKS, f, ensure_ascii=False)
    return f"Добавил: {text}"


def list_tasks():
    if not TASKS:
        return "Задач нет"
    lines = []
    for i, task in enumerate(sorted(TASKS, key=lambda t: t["priority"]), 1):
        lines.append(f"{i}) {task['text']}")
    return " ".join(lines)


TOOLS = [make_tool("add_task", "Добавить задачу в план.",
                   {"text": {"type": "string", "description": "Что сделать"},
                    "priority": {"type": "integer", "description": "Важность: 1 — самое важное"}}, ["text", "priority"]),
         make_tool("list_tasks", "Показать план: сначала самое важное.")]
FUNCTIONS = {"add_task": lambda args: add_task(args["text"], args["priority"]), "list_tasks": lambda args: list_tasks()}
SYSTEM = "Ты планировщик. Задачи добавляй и показывай только инструментами."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
