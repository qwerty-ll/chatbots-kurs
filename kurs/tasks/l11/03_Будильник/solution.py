# Задание 3. Будильник с проверкой
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool


def set_alarm(hour, minute):
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "Неверное время"
    return f"Будильник на {hour:02d}:{minute:02d}"


TOOLS = [make_tool("set_alarm", "Поставить будильник.",
                   {"hour": {"type": "integer", "description": "Час 0–23"},
                    "minute": {"type": "integer", "description": "Минуты 0–59"}}, ["hour", "minute"])]
FUNCTIONS = {"set_alarm": lambda args: set_alarm(args["hour"], args["minute"])}
SYSTEM = "Ты помощник с будильником. Ставь его только инструментом set_alarm."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
