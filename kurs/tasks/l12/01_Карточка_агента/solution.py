# Задание 1. Карточка агента
# Условие — в панели справа. Напиши программу ниже сам.

def make_system(agent):
    return f"Ты {agent['name']}, {agent['role']}. Правила: " + "; ".join(agent["rules"]) + "."


name = input("Имя агента: ").strip()
role = input("Роль: ").strip()
agent = {"name": name, "role": role, "rules": ["отвечай коротко", "не выдумывай факты"]}
print(make_system(agent))
