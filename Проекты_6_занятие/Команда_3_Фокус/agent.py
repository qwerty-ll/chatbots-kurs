# Модуль agent.py — готовый «цикл агента»: модель → инструмент → результат → модель → ответ.
#
# Подключение:   from agent import make_tool, agent_answer
#
#   TOOLS     — список описаний инструментов (make_tool) — их читает нейросеть
#   FUNCTIONS — словарь «имя инструмента -> функция», которая получает args (словарь)
#
#   messages = [{"role": "system", "content": "Ты помощник..."},
#               {"role": "user", "content": "Подбрось монетку"}]
#   print(agent_answer(messages, TOOLS, FUNCTIONS))

import json

from ai import chat


def make_tool(name, description, properties=None, required=None):
    """Собирает описание инструмента в формате, который понимает нейросеть."""
    return {"type": "function", "function": {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {},
                       "required": required or []},
    }}


def run_tool(functions, name, args):
    """Запускает инструмент по имени. Ошибки превращаем в текст для модели."""
    if name not in functions:
        return f"Нет инструмента {name}"
    try:
        return str(functions[name](args))
    except Exception as error:
        return f"Ошибка инструмента: {error}"


def agent_answer(messages, tools, functions, steps=5):
    """Модель -> инструмент -> результат -> модель -> ... -> итоговый ответ."""
    for _ in range(steps):                   # защита от бесконечного цикла
        message = chat(messages, tools=tools)
        if message is None:
            return "Нейросеть сейчас недоступна. Попробуй через минуту."
        if not message.tool_calls:           # инструменты не нужны — это и есть ответ
            return message.content or "(пустой ответ)"
        # модель просит вызвать инструменты: запоминаем её просьбу...
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments}}
                           for c in message.tool_calls],
        })
        # ...запускаем каждый инструмент и возвращаем результат модели
        for call in message.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = run_tool(functions, call.function.name, args)
            print(f"  🔧 {call.function.name}({args}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return f"Не получилось решить задачу за {steps} шагов."
