# Задание 4. Только разрешённые файлы
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

ALLOWED = ["правила.txt", "меню.txt"]


def read_file(name):
    if name not in ALLOWED:
        return "Нет доступа к этому файлу"
    try:
        with open(name, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Файл не найден"


TOOLS = [make_tool("read_file", "Прочитать файл школы: правила.txt или меню.txt.",
                   {"name": {"type": "string", "description": "Имя файла"}}, ["name"])]
FUNCTIONS = {"read_file": lambda args: read_file(args["name"])}
SYSTEM = "Ты школьный помощник. Читай только разрешённые файлы инструментом read_file."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
