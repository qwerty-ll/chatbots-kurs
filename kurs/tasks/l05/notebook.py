# Тетрадь урока 5. Свои инструменты: бот-агент
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Функция — кусок программы с именем
import random


def coin_flip():
    return random.choice(["Орёл", "Решка"])


print(coin_flip())
print(coin_flip())

# ЭТАП 2: Функция с параметром
def roll_dice(sides=6):
    return random.randint(1, sides)


print("Обычный кубик:", roll_dice())
print("Кубик на 20:", roll_dice(20))

# ЭТАП 3: Описание инструментов для нейросети
from agent import agent_answer, make_tool

TOOLS = [
    make_tool("coin_flip", "Подбросить монетку: орёл или решка."),
    make_tool("roll_dice", "Бросить игральный кубик.",
              {"sides": {"type": "integer", "description": "Число граней, по умолчанию 6"}}),
]
FUNCTIONS = {
    "coin_flip": lambda args: coin_flip(),
    "roll_dice": lambda args: roll_dice(args.get("sides", 6)),
}

# ЭТАП 4: Агент отвечает на один вопрос
messages = [{"role": "system", "content": "Ты весёлый помощник. Для монетки и кубика используй инструменты."},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))

# ЭТАП 5: Агент в цикле помнит разговор
messages = [{"role": "system", "content": "Ты весёлый помощник. Для монетки и кубика используй инструменты."}]
while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    messages.append({"role": "user", "content": text})
    answer = agent_answer(messages, TOOLS, FUNCTIONS)
    messages.append({"role": "assistant", "content": answer})
    print("Агент:", answer)
