import threading
import time
import schedule
from datetime import date, timedelta
import database as db
import logging
import asyncio

logging.basicConfig(level=logging.INFO)

def check_and_send_reminders():
    """Эслатмаларни текширади ва жўнатади"""
    import sqlite3
    try:
        with db.get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT DISTINCT user_id FROM subscriptions")
            users = c.fetchall()
    except Exception as e:
        logging.error(f"Фойдаланувчиларни олишда хатолик: {e}")
        users = []
    
    for (user_id,) in users:
        try:
            for days_ahead in [7, 3, 1]:
                upcoming = db.get_upcoming_billing(user_id, days_ahead=days_ahead)
                today = date.today()
                for sub_id, name, cost, curr, due_date, is_trial in upcoming:
                    days_left = (due_date - today).days
                    if days_left == days_ahead:
                        if not db.was_reminder_sent(sub_id, due_date):
                            if is_trial:
                                text = f"🔔 Триал '{name}' заканчивается {due_date.strftime('%d.%m.%Y')}! Осталось {days_left} дня!"
                            else:
                                text = f"💸 Через {days_left} дня списание {cost}{curr} за '{name}' - {due_date.strftime('%d.%m.%Y')}"
                            try:
                                import bot
                                if bot.send_reminder_to_user:
                                    asyncio.create_task(bot.send_reminder_to_user(user_id, text))
                                db.mark_reminder_sent(sub_id, user_id, due_date)
                            except Exception as e:
                                logging.error(f"Эслатма юборишда хатолик: {e}")
        except Exception as e:
            logging.error(f"Фойдаланувчи {user_id} учун эслатма текширишда хатолик: {e}")

def check_daily_report():
    """Ҳар куни ertalab статистика жўнатади"""
    import sqlite3
    try:
        with db.get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT DISTINCT user_id FROM users")
            users = c.fetchall()
    except Exception as e:
        logging.error(f"Кунлик отчёт учун фойдаланувчиларни олишда хатолик: {e}")
        users = []
    
    for (user_id,) in users:
        try:
            currency = db.get_user_currency(user_id)
            expenses_today = 0
            for exp in db.get_expenses(user_id, days=1):
                expenses_today += exp[1]
            if expenses_today > 0:
                text = f"📊 *Ежедневный отчёт*\n\n💰 Сегодня потрачено: {db.format_money(expenses_today, currency)}\n📅 {date.today().strftime('%d.%m.%Y')}"
                import bot
                if bot.send_reminder_to_user:
                    asyncio.create_task(bot.send_reminder_to_user(user_id, text))
        except Exception as e:
            logging.error(f"Кунлик отчёт юборишда хатолик: {e}")

def run_scheduler():
    schedule.every().day.at("09:00").do(check_and_send_reminders)
    schedule.every().day.at("20:00").do(check_daily_report)
    logging.info("Эслатмалар треди ишга тушди")
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_reminder_thread():
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()

send_reminder_to_user = None
