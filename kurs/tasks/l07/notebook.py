# Тетрадь урока 7. Бот-агент
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Инструмент — обычная функция
import random


def coin_flip():
    return random.choice(["Орёл", "Решка"])


print(coin_flip())

# ЭТАП 2: Описание инструмента и словарь функций
from agent import agent_answer, make_tool

TOOLS = [make_tool("coin_flip", "Подбросить монетку: орёл или решка.")]
FUNCTIONS = {"coin_flip": lambda args: coin_flip()}

# ЭТАП 3: Запускаем агента
messages = [{"role": "system", "content": "Ты бот-помощник. Если нужна монетка — используй инструмент."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
