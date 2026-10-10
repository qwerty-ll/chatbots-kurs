from ai import ask

topic = input("Что объяснить? ")
audience = input("Кому объяснить? ")
prompt = f"Объясни тему «{topic}» так, чтобы понял {audience}. Не больше 3 предложений."
print(ask(prompt))
