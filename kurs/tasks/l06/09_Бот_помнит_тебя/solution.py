# Задание 9. Бот, который помнит тебя
# Условие — в панели справа. Напиши программу ниже сам.
# Файл ai.py уже лежит рядом: from ai import ask, chat_text

import json
import os

from ai import chat_text

FILE = "memory.json"


def load_memory():
    if os.path.exists(FILE):
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"profile": {}, "history": []}


def save_memory(memory):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False)


def build_system_prompt(profile):
    facts = "; ".join(f"{key}: {value}" for key, value in profile.items())
    return f"Ты дружелюбный бот. Что ты знаешь о собеседнике: {facts}."


memory = load_memory()
if "имя" in memory["profile"]:
    print(f"С возвращением, {memory['profile']['имя']}!")
else:
    memory["profile"]["имя"] = input("Как тебя зовут? ").strip()
    save_memory(memory)
    print(f"Запомнил, {memory['profile']['имя']}!")

while True:
    text = input("Ты: ").strip()
    if text == "/exit":
        break
    if text.startswith("/remember "):
        key, value = text[10:].split("=", 1)
        memory["profile"][key.strip()] = value.strip()
        save_memory(memory)
        print("Запомнил!")
        continue
    question = {"role": "user", "content": text}
    messages = [{"role": "system", "content": build_system_prompt(memory["profile"])}] + memory["history"] + [question]
    answer = chat_text(messages)
    print("Бот:", answer)
    memory["history"].append(question)
    memory["history"].append({"role": "assistant", "content": answer})
    memory["history"] = memory["history"][-20:]
    save_memory(memory)
