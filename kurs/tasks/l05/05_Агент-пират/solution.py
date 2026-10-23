# Задание 5. Агент-пират: переводчик
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool


def to_pirate(text):
    text = text.lower()
    text = text.replace("привет", "йо-хо-хо")
    text = text.replace("друг", "юнга")
    text = text.replace("деньги", "дублоны")
    return text


TOOLS = [make_tool("to_pirate", "Перевести фразу на пиратский язык.",
                   {"text": {"type": "string", "description": "Фраза для перевода"}}, ["text"])]
FUNCTIONS = {"to_pirate": lambda args: to_pirate(args["text"])}

messages = [{"role": "system", "content": "Ты бот-переводчик. Для перевода на пиратский используй инструмент."},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
