from ai import ask

question = input("Твой вопрос: ")
q = question.lower().strip()
if "расписание" in q or "когда" in q:
    print("Занятия по средам и пятницам.")
elif "цена" in q or "стоит" in q:
    print("Бесплатно!")
else:
    print(ask(question, system="Ты бот кружка программирования. Отвечай коротко."))
