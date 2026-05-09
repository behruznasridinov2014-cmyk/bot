import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional
import logging
import time

DB_NAME = "finance_bot.db"
logging.basicConfig(level=logging.WARNING)

def get_db_connection():
    """Базага уланиш - блокировкани олдини олади"""
    for _ in range(5):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(0.5)
                continue
            raise
    raise Exception("Базага уланиш 5 мартадан кейин ҳам мабўл бўлмади")

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        budget REAL DEFAULT 0,
        currency TEXT DEFAULT '$',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
    except: pass
    
    # Подписки
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        cost REAL,
        currency TEXT DEFAULT '$',
        billing_day INTEGER DEFAULT 1,
        billing_date DATE,
        is_trial BOOLEAN DEFAULT 0,
        trial_end DATE,
        payment_method TEXT DEFAULT 'Карта',
        auto_renew BOOLEAN DEFAULT 1,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Расходы
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        currency TEXT DEFAULT '$',
        category TEXT,
        description TEXT,
        tags TEXT,
        expense_date DATE DEFAULT CURRENT_DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Напоминания
    c.execute('''CREATE TABLE IF NOT EXISTS reminders_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER,
        user_id INTEGER,
        reminder_date DATE,
        UNIQUE(subscription_id, reminder_date)
    )''')
    
    # Накопления
    c.execute('''CREATE TABLE IF NOT EXISTS savings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        currency TEXT DEFAULT '$',
        purpose TEXT,
        saving_date DATE DEFAULT CURRENT_DATE
    )''')
    
    # Цели
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        target_amount REAL,
        current_amount REAL DEFAULT 0,
        currency TEXT DEFAULT '$',
        deadline DATE,
        priority INTEGER DEFAULT 2,
        is_completed BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Доходы
    c.execute('''CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        currency TEXT DEFAULT '$',
        source TEXT,
        is_recurring BOOLEAN DEFAULT 0,
        income_date DATE DEFAULT CURRENT_DATE
    )''')
    
    # Долги
    c.execute('''CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        person_name TEXT,
        amount REAL,
        currency TEXT DEFAULT '$',
        debt_type TEXT DEFAULT 'owed_to_me',
        description TEXT,
        due_date DATE,
        is_paid BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Мультибюджет
    c.execute('''CREATE TABLE IF NOT EXISTS multiple_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        amount REAL,
        currency TEXT DEFAULT '$',
        spent REAL DEFAULT 0,
        period TEXT DEFAULT 'monthly',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Категории
    c.execute('''CREATE TABLE IF NOT EXISTS custom_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        icon TEXT DEFAULT '📝',
        color TEXT DEFAULT '#9E9E9E',
        is_active BOOLEAN DEFAULT 1,
        UNIQUE(user_id, name)
    )''')
    
    # Достижения
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        achievement_type TEXT,
        achievement_value INTEGER,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, achievement_type)
    )''')
    
    # Стандарт категориялар
    default_cats = [
        ('Еда', '🍔', '#4CAF50'), ('Транспорт', '🚗', '#2196F3'),
        ('Подписки', '🎬', '#9C27B0'), ('Дом', '🏠', '#FF9800'),
        ('Здоровье', '💊', '#F44336'), ('Одежда', '👕', '#E91E63'),
        ('Развлечения', '🎮', '#673AB7'), ('Образование', '📚', '#00BCD4'),
        ('Кафе', '☕', '#795548'), ('Подарки', '🎁', '#E91E63'), ('Другое', '📝', '#9E9E9E')
    ]
    for name, icon, color in default_cats:
        c.execute("INSERT OR IGNORE INTO custom_categories (user_id, name, icon, color) VALUES (0, ?, ?, ?)", (name, icon, color))
    
    conn.commit()
    conn.close()
    logging.info("База инициализация қилинди")

# ========== ФОЙДАЛАНУВЧИЛАР ==========
def get_user(user_id: int) -> Tuple:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT budget, currency, language FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            conn.close()
            return row
    except: pass
    
    try:
        c.execute("SELECT budget, currency FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            conn.close()
            return (row[0], row[1], 'ru')
        else:
            c.execute("INSERT INTO users (user_id, budget, currency) VALUES (?, 0, '$')", (user_id,))
            conn.commit()
            conn.close()
            return (0.0, '$', 'ru')
    except:
        conn.close()
        return (0.0, '$', 'ru')

def get_user_currency(user_id: int) -> str:
    return get_user(user_id)[1]

def set_user_budget(user_id: int, budget: float, currency: str = '$'):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, budget, currency) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET budget = ?, currency = ?", 
              (user_id, budget, currency, budget, currency))
    conn.commit()
    conn.close()

# ========== ПОДПИСКИ ==========
def add_subscription(user_id: int, name: str, cost: float, billing_day: int, currency: str = '$', 
                     is_trial: bool = False, trial_end_date: str = None, payment_method: str = 'Карта', 
                     auto_renew: bool = True, notes: str = ""):
    conn = get_db_connection()
    c = conn.cursor()
    if billing_day < 1 or billing_day > 31:
        billing_day = 1
    today = date.today()
    try:
        bill_dt = date(today.year, today.month, billing_day)
        if bill_dt < today:
            if today.month == 12:
                bill_dt = date(today.year + 1, 1, billing_day)
            else:
                try:
                    bill_dt = date(today.year, today.month + 1, billing_day)
                except ValueError:
                    bill_dt = date(today.year, today.month + 1, 1) + timedelta(days=27)
    except ValueError:
        bill_dt = date(today.year, today.month, 28) + timedelta(days=4)
        bill_dt = bill_dt - timedelta(days=bill_dt.day - 1)
    
    c.execute('''INSERT INTO subscriptions 
                 (user_id, name, cost, currency, billing_day, billing_date, is_trial, trial_end, payment_method, auto_renew, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, name, cost, currency, billing_day, bill_dt.isoformat(), is_trial, trial_end_date, payment_method, auto_renew, notes))
    conn.commit()
    conn.close()

def get_subscriptions(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, cost, currency, billing_day, billing_date, is_trial, trial_end, payment_method, auto_renew, notes FROM subscriptions WHERE user_id = ? ORDER BY billing_day", (user_id,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        try:
            c.execute("SELECT id, name, cost, currency, billing_date, is_trial, trial_end, payment_method, auto_renew, notes FROM subscriptions WHERE user_id = ?", (user_id,))
            rows = c.fetchall()
            conn.close()
            result = []
            for r in rows:
                bill_day = 1
                try:
                    if r[4]:
                        bill_day = datetime.fromisoformat(r[4]).day
                except:
                    bill_day = 1
                result.append((r[0], r[1], r[2], r[3], bill_day, r[4], r[5], r[6], r[7], r[8], r[9]))
            return result
        except:
            conn.close()
            return []

def get_subscription_by_id(sub_id: int, user_id: int) -> Optional[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM subscriptions WHERE id = ? AND user_id = ?", (sub_id, user_id))
    row = c.fetchone()
    conn.close()
    return row

def delete_subscription(sub_id: int, user_id: int) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions WHERE id = ? AND user_id = ?", (sub_id, user_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_subscription(sub_id: int, user_id: int, **kwargs):
    conn = get_db_connection()
    c = conn.cursor()
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value)
    values.extend([sub_id, user_id])
    if updates:
        c.execute(f"UPDATE subscriptions SET {', '.join(updates)} WHERE id = ? AND user_id = ?", values)
    conn.commit()
    conn.close()

def get_total_monthly_cost(user_id: int) -> float:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT SUM(cost) FROM subscriptions WHERE user_id = ? AND is_trial = 0", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row[0] else 0.0

# ========== РАСХОДЫ ==========
def add_expense(user_id: int, amount: float, category: str, description: str = "", currency: str = '$', tags: str = ""):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO expenses (user_id, amount, currency, category, description, tags)
                 VALUES (?, ?, ?, ?, ?, ?)''', (user_id, amount, currency, category, description, tags))
    conn.commit()
    conn.close()
    check_achievements(user_id)

def get_expenses(user_id: int, days: int = 30) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, amount, currency, category, description, tags, expense_date 
                 FROM expenses 
                 WHERE user_id = ? AND expense_date >= date('now', ?) 
                 ORDER BY expense_date DESC''', (user_id, f'-{days} days'))
    rows = c.fetchall()
    conn.close()
    return rows

def get_total_expenses_last_days(user_id: int, days: int = 30) -> float:
    total = 0.0
    for row in get_expenses(user_id, days):
        total += row[1]
    return total

def get_expenses_by_category(user_id: int, days: int = 30) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT category, SUM(amount), COUNT(*) 
                 FROM expenses 
                 WHERE user_id = ? AND expense_date >= date('now', ?)
                 GROUP BY category''', (user_id, f'-{days} days'))
    rows = c.fetchall()
    conn.close()
    return {row[0]: {"amount": row[1], "count": row[2]} for row in rows}

def get_daily_expenses(user_id: int, days: int = 30) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT expense_date, SUM(amount), COUNT(*) 
                 FROM expenses 
                 WHERE user_id = ? AND expense_date >= date('now', ?)
                 GROUP BY expense_date''', (user_id, f'-{days} days'))
    rows = c.fetchall()
    conn.close()
    return {row[0]: {"amount": row[1], "count": row[2]} for row in rows}

def get_trend_analysis(user_id: int) -> dict:
    expenses_now = get_total_expenses_last_days(user_id, 30)
    expenses_prev = get_total_expenses_last_days(user_id, 60) - expenses_now
    if expenses_prev > 0:
        change = ((expenses_now - expenses_prev) / expenses_prev) * 100
    else:
        change = 0
    return {
        "current": expenses_now,
        "previous": expenses_prev,
        "change_percent": change,
        "trend": "📈 растут" if change > 5 else "📉 падают" if change < -5 else "➡️ стабильны"
    }

# ========== ДОХОДЫ ==========
def add_income(user_id: int, amount: float, currency: str, source: str, is_recurring: bool = False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO incomes (user_id, amount, currency, source, is_recurring)
                 VALUES (?, ?, ?, ?, ?)''', (user_id, amount, currency, source, is_recurring))
    conn.commit()
    conn.close()

def get_total_incomes_last_days(user_id: int, days: int = 30) -> float:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM incomes WHERE user_id = ? AND income_date >= date('now', ?)", (user_id, f'-{days} days'))
    total = c.fetchone()[0] or 0
    conn.close()
    return total

# ========== НАПОМИНАНИЯ ==========
def get_upcoming_billing(user_id: int, days_ahead: int = 7) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    today = date.today()
    try:
        c.execute('''SELECT id, name, cost, currency, billing_day, billing_date, is_trial, trial_end 
                     FROM subscriptions WHERE user_id = ?''', (user_id,))
        subs = c.fetchall()
    except:
        conn.close()
        return []
    
    upcoming = []
    for sub in subs:
        sub_id, name, cost, currency, billing_day, bill_date_str, is_trial, trial_end = sub
        if is_trial and trial_end:
            end_date = date.fromisoformat(trial_end)
            if today <= end_date <= today + timedelta(days=days_ahead):
                upcoming.append((sub_id, name, cost, currency, end_date, True))
        else:
            try:
                next_date = date.fromisoformat(bill_date_str)
                if next_date < today:
                    if today.month == 12:
                        next_date = date(today.year + 1, 1, billing_day)
                    else:
                        try:
                            next_date = date(today.year, today.month + 1, billing_day)
                        except ValueError:
                            next_date = date(today.year, today.month + 1, 1) + timedelta(days=27)
                if today <= next_date <= today + timedelta(days=days_ahead):
                    upcoming.append((sub_id, name, cost, currency, next_date, False))
            except:
                continue
    conn.close()
    return sorted(upcoming, key=lambda x: x[4])

def was_reminder_sent(sub_id: int, reminder_date: date) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM reminders_sent WHERE subscription_id = ? AND reminder_date = ?", (sub_id, reminder_date.isoformat()))
    row = c.fetchone()
    conn.close()
    return row is not None

def mark_reminder_sent(sub_id: int, user_id: int, reminder_date: date):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO reminders_sent (subscription_id, user_id, reminder_date) VALUES (?, ?, ?)",
              (sub_id, user_id, reminder_date.isoformat()))
    conn.commit()
    conn.close()

# ========== НАКОПЛЕНИЯ ==========
def add_saving(user_id: int, amount: float, currency: str = '$', purpose: str = "") -> float:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO savings (user_id, amount, currency, purpose) VALUES (?, ?, ?, ?)''', (user_id, amount, currency, purpose))
    conn.commit()
    c.execute("SELECT SUM(amount) FROM savings WHERE user_id = ? AND currency = ?", (user_id, currency))
    total = c.fetchone()[0] or 0
    conn.close()
    return total

def get_total_savings(user_id: int, currency: str = '$') -> float:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM savings WHERE user_id = ? AND currency = ?", (user_id, currency))
    total = c.fetchone()[0] or 0
    conn.close()
    return total

# ========== ЦЕЛИ ==========
def add_goal(user_id: int, name: str, target_amount: float, currency: str = '$', deadline: str = None, priority: int = 2):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO goals (user_id, name, target_amount, currency, deadline, priority)
                 VALUES (?, ?, ?, ?, ?, ?)''', (user_id, name, target_amount, currency, deadline, priority))
    conn.commit()
    conn.close()

def get_goals(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, target_amount, current_amount, currency, deadline, priority, is_completed FROM goals WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_auto_goal_suggestion(user_id: int) -> str:
    expenses = get_total_expenses_last_days(user_id, 30)
    if expenses > 0:
        suggested = expenses * 0.2
        return f"💡 Совет: откладывайте {format_money(suggested, get_user_currency(user_id))} в месяц - это 20% от ваших расходов!"
    return "💡 Начните откладывать 10% от каждого дохода!"

# ========== ДОЛГИ ==========
def add_debt(user_id: int, person_name: str, amount: float, currency: str, debt_type: str, description: str = "", due_date: str = None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO debts (user_id, person_name, amount, currency, debt_type, description, due_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', (user_id, person_name, amount, currency, debt_type, description, due_date))
    conn.commit()
    conn.close()

def get_debts(user_id: int, debt_type: str = None) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    if debt_type:
        c.execute("SELECT id, person_name, amount, currency, description, due_date, is_paid FROM debts WHERE user_id = ? AND debt_type = ? AND is_paid = 0", (user_id, debt_type))
    else:
        c.execute("SELECT id, person_name, amount, currency, debt_type, description, due_date, is_paid FROM debts WHERE user_id = ? AND is_paid = 0", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_debt_summary(user_id: int) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM debts WHERE user_id = ? AND debt_type = 'owed_to_me' AND is_paid = 0", (user_id,))
    owed_to_me = c.fetchone()[0] or 0
    c.execute("SELECT SUM(amount) FROM debts WHERE user_id = ? AND debt_type = 'i_owe' AND is_paid = 0", (user_id,))
    i_owe = c.fetchone()[0] or 0
    conn.close()
    return {"owed_to_me": owed_to_me, "i_owe": i_owe}

# ========== МУЛЬТИБЮДЖЕТ ==========
def add_multiple_budget(user_id: int, name: str, amount: float, currency: str = '$', period: str = 'monthly'):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO multiple_budgets (user_id, name, amount, currency, period)
                 VALUES (?, ?, ?, ?, ?)''', (user_id, name, amount, currency, period))
    conn.commit()
    conn.close()

def get_multiple_budgets(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, amount, currency, spent, period FROM multiple_budgets WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_budget_spent(budget_id: int, user_id: int, amount: float):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE multiple_budgets SET spent = spent + ? WHERE id = ? AND user_id = ?", (amount, budget_id, user_id))
    conn.commit()
    conn.close()

# ========== КАТЕГОРИЯЛАР ==========
def get_categories(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, icon, color FROM custom_categories WHERE user_id = ? OR user_id = 0 ORDER BY name", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_custom_category(user_id: int, name: str, icon: str = "📝", color: str = "#9E9E9E"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO custom_categories (user_id, name, icon, color) VALUES (?, ?, ?, ?)", (user_id, name, icon, color))
    conn.commit()
    conn.close()

def delete_custom_category(cat_id: int, user_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM custom_categories WHERE id = ? AND user_id = ? AND user_id != 0", (cat_id, user_id))
    conn.commit()
    conn.close()

# ========== ДОСТИЖЕНИЯ ==========
def check_achievements(user_id: int):
    conn = get_db_connection()
    c = conn.cursor()
    expenses_count = c.execute("SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)).fetchone()[0]
    if expenses_count >= 10 and not c.execute("SELECT 1 FROM achievements WHERE user_id = ? AND achievement_type = 'first_10_expenses'", (user_id,)).fetchone():
        c.execute("INSERT INTO achievements (user_id, achievement_type, achievement_value) VALUES (?, ?, ?)", (user_id, 'first_10_expenses', expenses_count))
    if expenses_count >= 50 and not c.execute("SELECT 1 FROM achievements WHERE user_id = ? AND achievement_type = 'fifty_expenses'", (user_id,)).fetchone():
        c.execute("INSERT INTO achievements (user_id, achievement_type, achievement_value) VALUES (?, ?, ?)", (user_id, 'fifty_expenses', expenses_count))
    if expenses_count >= 100 and not c.execute("SELECT 1 FROM achievements WHERE user_id = ? AND achievement_type = 'hundred_expenses'", (user_id,)).fetchone():
        c.execute("INSERT INTO achievements (user_id, achievement_type, achievement_value) VALUES (?, ?, ?)", (user_id, 'hundred_expenses', expenses_count))
    conn.commit()
    conn.close()

def get_achievements(user_id: int) -> List[Tuple]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT achievement_type, achievement_value, unlocked_at FROM achievements WHERE user_id = ? ORDER BY unlocked_at", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_achievements(user_id: int) -> List[Tuple]:
    return get_achievements(user_id)

# ========== ЁРДАМЧИ ФУНКЦИЯЛАР ==========
def validate_billing_day(day_str: str):
    try:
        day = int(day_str)
        if 1 <= day <= 31:
            return True, day, None
        else:
            return False, None, "❌ День должен быть от 1 до 31!"
    except:
        return False, None, "❌ Введите число! Например: 5, 15, 31"

def format_billing_day(day: int) -> str:
    return f"{day}-го числа"

def format_money(amount: float, currency: str = '$') -> str:
    amount = round(amount, 2)
    if amount.is_integer():
        formatted = f"{int(amount):,}".replace(",", " ")
        return f"{formatted}{currency}"
    else:
        integer_part = int(amount)
        fractional = int(round((amount - integer_part) * 100))
        formatted_int = f"{integer_part:,}".replace(",", " ")
        return f"{formatted_int}.{fractional:02d}{currency}"
    