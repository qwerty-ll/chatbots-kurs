# Тетрадь урока 8. Данные для агента: словари и JSON
# Учитель печатает этот код на проекторе по этапам. Ученики пишут за ним в своей тетради.
# Метка «# ЭТАП N: ...» отделяет этапы. Код этапа — всё до следующей метки.

# ЭТАП 1: Словарь
card = {"имя": "Аня", "класс": "7Б", "предмет": "информатика"}
print(card["имя"], card.get("рост", "нет данных"))

# ЭТАП 2: Словарь → JSON-текст
import json

text = json.dumps(card, ensure_ascii=False)
print(text)

# ЭТАП 3: JSON-текст → словарь
data = json.loads(text)
print(data["класс"])

# ЭТАП 4: Инструмент отвечает JSON
WEATHER = {"Москва": {"temp": 3, "sky": "облачно"}}


def weather(city):
    if city not in WEATHER:
        return json.dumps({"error": "Нет данных"}, ensure_ascii=False)
    return json.dumps({"city": city, **WEATHER[city]}, ensure_ascii=False)


print(weather("Москва"))

# ЭТАП 5: Вызов инструмента вручную — как в agent.py
FUNCTIONS = {"weather": lambda args: weather(args["city"])}
call = json.loads('{"name": "weather", "args": {"city": "Москва"}}')
print(FUNCTIONS[call["name"]](call["args"]))
