# Задание 6. Память разговора: только последнее
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

SYSTEM = "Ты дружелюбный собеседник. Отвечай коротко."
messages = [{"role": "system", "content": SYSTEM}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    messages = [messages[0]] + messages[1:][-4:]
    answer = agent_answer(messages, [], {})
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
