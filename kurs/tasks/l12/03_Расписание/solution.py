# Задание 3. Помощник по расписанию
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

SCHEDULE = {"понедельник": ["математика", "русский", "физкультура"], "вторник": ["история", "информатика"]}


def schedule(day):
    if day not in SCHEDULE:
        return "В этот день уроков нет"
    return ", ".join(SCHEDULE[day])


TOOLS = [make_tool("schedule", "Узнать уроки на день недели.",
                   {"day": {"type": "string", "description": "День недели маленькими буквами"}}, ["day"])]
FUNCTIONS = {"schedule": lambda args: schedule(args["day"])}
SYSTEM = "Ты школьный помощник. Расписание бери только из инструмента schedule."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
