# Тетрадь урока 12. Свой агент: итоговый проект
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Карточка агента
AGENT = {"name": "Робин", "role": "помощник библиотеки", "rules": ["отвечай коротко", "не выдумывай книги"]}


def make_system(agent):
    return f"Ты {agent['name']}, {agent['role']}. Правила: " + "; ".join(agent["rules"]) + "."


print(make_system(AGENT))

# ЭТАП 2: Поиск по списку словарей
import json

BOOKS = [{"title": "Капитанская дочка", "author": "Пушкин"},
         {"title": "Муму", "author": "Тургенев"}]


def find_books(author):
    found = [b["title"] for b in BOOKS if author.lower() in b["author"].lower()]
    return json.dumps(found, ensure_ascii=False) if found else "Ничего не нашёл"


print(find_books("пушкин"))

# ЭТАП 3: Агент-библиотекарь
from agent import agent_answer, make_tool

TOOLS = [make_tool("find_books", "Найти книги автора.", {"author": {"type": "string", "description": "Фамилия автора"}}, ["author"])]
FUNCTIONS = {"find_books": lambda args: find_books(args["author"])}

# ЭТАП 4: Цикл с короткой памятью
messages = [{"role": "system", "content": make_system(AGENT)}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    messages = [messages[0]] + messages[1:][-6:]
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
