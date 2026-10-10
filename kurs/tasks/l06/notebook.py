# Тетрадь урока 6. Бот, который помнит тебя
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Словарь — карточка пользователя
profile = {"имя": "Аня", "еда": "пицца"}
profile["хобби"] = "футбол"
for key, value in profile.items():
    print(f"{key}: {value}")

# ЭТАП 2: Сохраняем и читаем JSON
import json
import os

FILE = "memory.json"


def load_memory():
    if os.path.exists(FILE):
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"profile": {}, "history": []}


def save_memory(memory):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

# ЭТАП 3: Профиль → промпт
from ai import chat_text


def build_system_prompt(profile):
    facts = "; ".join(f"{key}: {value}" for key, value in profile.items())
    return f"Ты дружелюбный бот. Что ты знаешь о собеседнике: {facts}."


memory = load_memory()
question = {"role": "user", "content": "Что мне приготовить на ужин?"}
messages = [{"role": "system", "content": build_system_prompt(memory["profile"])}] + memory["history"] + [question]
print(chat_text(messages))
