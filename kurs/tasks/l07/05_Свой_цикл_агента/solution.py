# Задание 5. Свой цикл агента
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py лежит рядом: from ai import chat. agent.py в этом задании не используем!

import random

from ai import chat


def lucky_number():
    return random.randint(1, 100)


TOOLS = [{"type": "function", "function": {
    "name": "lucky_number", "description": "Назвать случайное счастливое число от 1 до 100.",
    "parameters": {"type": "object", "properties": {}, "required": []}}}]
FUNCTIONS = {"lucky_number": lucky_number}

messages = [{"role": "system", "content": "Ты бот-помощник. Для счастливого числа используй инструмент."},
            {"role": "user", "content": input("Ты: ")}]
message = chat(messages, tools=TOOLS)
if message.tool_calls:
    call = message.tool_calls[0]
    messages.append({"role": "assistant", "content": message.content or "", "tool_calls": [
        {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}}]})
    result = FUNCTIONS[call.function.name]()
    print(f"  🔧 {call.function.name} -> {result}")
    messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
    message = chat(messages, tools=TOOLS)
print("Агент:", message.content)
