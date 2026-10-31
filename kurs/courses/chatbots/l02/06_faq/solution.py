q = input("Вопрос: ").lower().strip()
if "расписание" in q or "когда" in q:
    print("Занятия по средам и пятницам.")
elif "цена" in q or "стоит" in q:
    print("Бесплатно!")
elif "адрес" in q or "где" in q:
    print("Кабинет 305.")
else:
    print("Я пока не понял вопрос.")
