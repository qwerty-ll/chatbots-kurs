# Задание 5. Агент-переводчик
# Условие — в панели справа. Напиши программу ниже сам.
# Рядом лежат ai.py и agent.py: from agent import make_tool, agent_answer

from agent import agent_answer, make_tool

WORDS = {
    "кот": {"en": "cat", "de": "Katze"},
    "собака": {"en": "dog", "de": "Hund"},
    "дом": {"en": "house", "de": "Haus"},
}


def translate(word, lang):
    if word not in WORDS:
        return f"Не знаю слова {word}"
    if lang not in WORDS[word]:
        return "Не знаю такой язык"
    return WORDS[word][lang]


TOOLS = [make_tool("translate", "Перевести русское слово на английский (en) или немецкий (de).",
                   {"word": {"type": "string", "description": "Русское слово"},
                    "lang": {"type": "string", "description": "Код языка: en или de"}},
                   ["word", "lang"])]
FUNCTIONS = {"translate": lambda args: translate(args["word"], args["lang"])}
SYSTEM = "Ты переводчик. Переводы бери только из инструмента translate."

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": input("Ты: ")}]
print("Агент:", agent_answer(messages, TOOLS, FUNCTIONS))
