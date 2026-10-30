# Задание 2. Агент по карточке
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

AGENT = {"name": "Робин", "role": "помощник библиотеки", "rules": ["отвечай коротко", "не выдумывай книги"]}


def make_system(agent):
    return f"Ты {agent['name']}, {agent['role']}. Правила: " + "; ".join(agent["rules"]) + "."


messages = [{"role": "system", "content": make_system(AGENT)}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, [], {})
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
