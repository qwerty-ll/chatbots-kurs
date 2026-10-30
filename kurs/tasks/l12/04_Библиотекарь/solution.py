# Задание 4. Агент-библиотекарь
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

import json

from agent import agent_answer, make_tool

BOOKS = [
    {"title": "Капитанская дочка", "author": "Пушкин"},
    {"title": "Евгений Онегин", "author": "Пушкин"},
    {"title": "Муму", "author": "Тургенев"},
    {"title": "Каштанка", "author": "Чехов"},
]


def find_books(author):
    found = []
    for book in BOOKS:
        if author.lower() in book["author"].lower():
            found.append(book["title"])
    if not found:
        return "Ничего не нашёл"
    return json.dumps(found, ensure_ascii=False)


TOOLS = [make_tool("find_books", "Найти книги автора в библиотеке.",
                   {"author": {"type": "string", "description": "Фамилия автора"}}, ["author"])]
FUNCTIONS = {"find_books": lambda args: find_books(args["author"])}
SYSTEM = "Ты библиотекарь. Книги ищи только инструментом find_books, не выдумывай."

messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
