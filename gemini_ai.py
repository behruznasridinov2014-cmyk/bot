import google.generativeai as genai
import os
from dotenv import load_dotenv
from typing import List, Tuple
import database as db

load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def chat_with_gemini(user_message: str, user_id: int = None) -> str:
    """Простой чат с AI. Если передан user_id, может добавить контекст."""
    if not model:
        return "❌ AI не настроен: отсутствует GEMINI_API_KEY"
    
    context = ""
    if user_id:
        budget = db.get_user_budget(user_id)
        expenses_total = db.get_total_expenses_last_days(user_id, 30)
        subs_total = db.get_total_monthly_cost(user_id)
        context = f"Пользователь: бюджет {budget} USD, траты за месяц {expenses_total:.2f} USD, подписки {subs_total:.2f} USD/мес. "
    
    prompt = f"{context}Вопрос: {user_message}\nОтветь дружелюбно, коротко, по делу."
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Ошибка AI: {str(e)}"

def predict_next_month_expenses(user_id: int) -> str:
    """Прогноз расходов на следующий месяц на основе истории + подписок"""
    if not model:
        return "AI не доступен"
    
    # Собираем данные
    expenses = db.get_expenses(user_id, days=90)
    # Группируем по категориям
    cats = {}
    for e in expenses:
        cat = e[2] if e[2] else "Другое"
        cats[cat] = cats.get(cat, 0) + e[1]
    subs = db.get_subscriptions(user_id)
    subs_info = [(s[1], s[2]) for s in subs if not s[4]]  # только не триалы
    budget = db.get_user_budget(user_id)
    
    prompt = f"""
    У пользователя бюджет: {budget} USD.
    Средние траты по категориям за 3 месяца: {cats}
    Активные платные подписки: {subs_info} (суммарно {sum(c[1] for c in subs_info)} USD/мес)
    Дай прогноз общих расходов на следующий месяц (примерно), укажи, можно ли сэкономить и на чём.
    Ответ напиши в 2-3 предложениях, конкретно.
    """
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Ошибка прогноза: {e}"
    