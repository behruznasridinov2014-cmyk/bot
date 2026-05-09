import logging
import os
import re
import asyncio
import random
import json
from datetime import date, timedelta, datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import io
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import database as db
import reminders

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Состояния диалогов
ADD_SUB_NAME, ADD_SUB_COST, ADD_SUB_CURRENCY, ADD_SUB_DAY, ADD_SUB_TRIAL, ADD_SUB_TRIAL_END, ADD_SUB_PAYMENT, ADD_SUB_AUTO_RENEW, ADD_SUB_NOTES = range(9)
ADD_EXPENSE_AMOUNT, ADD_EXPENSE_CURRENCY, ADD_EXPENSE_CATEGORY, ADD_EXPENSE_DESC, ADD_EXPENSE_TAGS = range(10, 15)
SET_BUDGET_AMOUNT, SET_BUDGET_CURRENCY = range(15, 17)
ADD_SAVING_AMOUNT, ADD_SAVING_CURRENCY, ADD_SAVING_PURPOSE = range(17, 20)
ADD_GOAL_NAME, ADD_GOAL_AMOUNT, ADD_GOAL_CURRENCY, ADD_GOAL_DEADLINE, ADD_GOAL_PRIORITY = range(20, 25)
ADD_INCOME_AMOUNT, ADD_INCOME_CURRENCY, ADD_INCOME_SOURCE, ADD_INCOME_RECURRING = range(25, 29)
EDIT_SUBSCRIPTION_ID, EDIT_SUBSCRIPTION_FIELD, EDIT_SUBSCRIPTION_VALUE = range(29, 32)
ADD_DEBT_TYPE, ADD_DEBT_NAME, ADD_DEBT_AMOUNT, ADD_DEBT_CURRENCY, ADD_DEBT_WHO, ADD_DEBT_WHEN = range(32, 38)
ADD_MULTI_BUDGET_NAME, ADD_MULTI_BUDGET_AMOUNT, ADD_MULTI_BUDGET_CURRENCY = range(38, 41)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Валюты
CURRENCIES = ['$ USD', '€ EUR', '₽ RUB', '₸ KZT', '¥ JPY', '₩ KRW', '₴ UAH', '₺ TRY', '💵 UZS']
CURRENCY_SYMBOLS = {
    '$ USD': '$', '€ EUR': '€', '₽ RUB': '₽', '₸ KZT': '₸',
    '¥ JPY': '¥', '₩ KRW': '₩', '₴ UAH': '₴', '₺ TRY': '₺', '💵 UZS': 'UZS'
}

# Популярные подписки
POPULAR_SUBSCRIPTIONS = [
    "Netflix", "Spotify", "YouTube Premium", "Apple Music", "Amazon Prime",
    "Disney+", "HBO Max", "CapCut Pro", "NordVPN", "ExpressVPN",
    "ChatGPT Plus", "Midjourney", "Canva Pro", "Adobe", "Microsoft 365",
    "Google One", "iCloud+", "Telegram Premium", "Tinder Plus", "Duolingo Plus"
]

# Способы оплаты
PAYMENT_METHODS = ['💳 Карта', '📱 Мобильный', '💰 Наличные', '🏦 Банк', '🔄 Автоплатёж']

# Категории расходов
EXPENSE_CATEGORIES = {
    '🍔 Еда': 'Еда', '🚗 Транспорт': 'Транспорт', '🎬 Подписки': 'Подписки',
    '🏠 Дом': 'Дом', '💊 Здоровье': 'Здоровье', '👕 Одежда': 'Одежда',
    '🎮 Развлечения': 'Развлечения', '📚 Образование': 'Образование', '📝 Другое': 'Другое'
}

def format_money(amount: float, currency: str = '$') -> str:
    """Деньгини форматлайди: 1 234 567$"""
    amount = round(amount, 2)
    if amount.is_integer():
        formatted = f"{int(amount):,}".replace(",", " ")
        return f"{formatted}{currency}"
    else:
        integer_part = int(amount)
        fractional = int(round((amount - integer_part) * 100))
        formatted_int = f"{integer_part:,}".replace(",", " ")
        return f"{formatted_int}.{fractional:02d}{currency}"

def parse_money(text: str) -> float:
    """Матндан пулни парс қилади"""
    cleaned = re.sub(r'[^\d\.,]', '', text)
    cleaned = cleaned.replace(' ', '').replace(',', '')
    if '.' in cleaned:
        return float(cleaned)
    return float(cleaned)

def ai_response(message: str, budget_info: str = "", context_history: list = None) -> str:
    """AI жавоб беради, контекстни эслаб"""
    msg = message.lower()
    
    # Контекстни сақлаш учун
    if context_history is None:
        context_history = []
    
    # Категориялар бўйича жавоблар
    if any(w in msg for w in ['еда', 'кушать', 'дешёво', 'готовить', 'продукты', 'рынок', 'овқат']):
        return random.choice([
            "🍔 Савдо қилишда бозордан харид қилинг — супермаркетдан 20-30% арзон!",
            "🥘 Уйда кўп порцияли тайёрланг ва музлатиб қўйинг — вақт ва пулни тежайди!",
            "🛒 Харид рўйхатини олдиндан тузинг ва оч қоринга борманг!",
            "🍚 Гуруч, картошка, тухум, мавсумий сабзавотлар — арзон ва тўйимли асос!"
        ])
    
    if any(w in msg for w in ['подписк', 'netflix', 'spotify', 'youtube', 'telegram', 'vpn', 'obuna']):
        return random.choice([
            "📱 Ойида бир марта подпискаларни текшириб чиқинг — ишлатилмайдиганларини ўчиринг!",
            "👨‍👩‍👧 Дўстларингиз билан семейный тарифни бўлишинг — ярмига тўлайсиз!",
            "🔄 Триални синаб кўринг ва дарҳол ўчириб қўйинг!",
            "📺 Бепул альтернативалар: YouTube AdBlock билан, кутубхоналар!"
        ])
    
    if any(w in msg for w in ['бюджет', 'сэкономить', 'деньги', 'копить', 'зарплат', 'экономия', 'byudjet', 'tejash']):
        return random.choice([
            f"💰 {budget_info}50/30/20 қоидаси: 50% заруриятларга, 30% хоҳишларга, 20% жамғармага!",
            "🎯 Ҳар ойликдан 10% дарҳол ажратиб қўйинг — бу темир қоида!",
            "📊 2 ҳафта давомида харажатларни ёзиб боринг — пул қаерга кетаётганини кўрасиз!",
            "☕ Бир дона кофедан воз кечиш = ойига 50-100 минг сўм тежаш!"
        ])
    
    if any(w in msg for w in ['долг', 'кредит', 'қарз', 'qarz', 'бердим', 'олдим']):
        return random.choice([
            "💰 Қарзларни ёзиб боришни бошланг! 'Долги/Кредитлар' кнопкаси орқали қўшинг.",
            "📝 Қарзларни муддати билан бирга ёзинг ва эслатмаларни ёқинг!",
            "🎯 Қарзларни тўлаш учун алоҳида бюджет ажратинг — 20% қоидаси ёрдам беради!"
        ])
    
    if any(w in msg for w in ['тренд', 'статистика', 'ўсиш', 'pasayish', 'o\'sish']):
        return random.choice([
            "📈 Трендларни кузатиш учун 'Статистика' бўлимида график расмлар мавжуд!",
            "📊 Харажатларнинг ўсиш ёки пасайишини аниқ кўриш учун Pie chart ишлатинг!",
            "📉 Агар харажатлар кўпайиб кетаётган бўлса, бюджетни қайта кўриб чиқинг!"
        ])
    
    if any(w in msg for w in ['достижени', 'достижения', 'ютуқ', 'yutuq', 'трат', 'trat']):
        return random.choice([
            "🏆 10, 50, 100 тратга эришганингизда фаранг! Кузатиб боринг!",
            "🏅 Достиженияларни 'Достижения' кнопкаси орқали кўришингиз мумкин!",
            "🎖️ Ҳар қандай молиявий ютуғингизни нишонланг — бу ментал жанг!"
        ])
    
    if any(w in msg for w in ['мультибюджет', 'multibyudjet', 'алохида бюджет', 'alohida']):
        return random.choice([
            "📊 Мультибюджет ёрдамида турли мақсадлар учун алоҳида бюджетлар тузинг!",
            "💰 Алоҳида бюджетлар: Таом, Транспорт, КИЙИМ-КЕЧАК — ҳаммаси алоҳида!",
            "📝 Ҳар бир категория учун ўз бюджетини белгиланг ва харажатларни назорат қилинг!"
        ])
    
    if any(w in msg for w in ['авто-цель', 'автоцель', 'auto-target', 'taklif']):
        return random.choice([
            "🎯 Доход қўшганингизда 20% ажратишни таклиф қиламан! Бу тежаш қоидаси!",
            "💰 Ҳар бир киримдан 20% дарҳол жамғармага ажратинг — автоматик цель!", 
            "📈 Авто-цель таклифи: Зарплатадан 20% = келажагингиз учун инвестиция!"
        ])
    
    if any(w in msg for w in ['привет', 'здравствуй', 'hi', 'hello', 'ку', 'салом', 'assalom']):
        return f"👋 Ассалому алайкум! {budget_info}Қандай ёрдам бера оламан?"
    
    if any(w in msg for w in ['smart', 'напоминани', 'eslatma', 'авто']):
        return random.choice([
            "🔔 Smart-напоминания: 7, 3, 1 кун олдин эслатаман!",
            "⏰ Подпискалар муддати тугашига 7, 3, 1 кун қолганда эслатма юбораман!",
            "📅 Триал тугашига олдиндан эслатиб қўяман — бюджетдан чиқиб кетманг!"
        ])
    
    return f"🤖 {budget_info}Харажатларни ёзиб боринг, кераксиз подпискаларни ўчиринг, даромаднинг 20% жамғармага ажратинг!"

def get_main_keyboard():
    """Асосий меню кнопкалари"""
    buttons = [
        [KeyboardButton("📋 Мои подписки"), KeyboardButton("➕ Добавить подписку")],
        [KeyboardButton("💰 Бюджет"), KeyboardButton("💸 Добавить трату")],
        [KeyboardButton("📈 Добавить доход"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🤖 AI Помощник"), KeyboardButton("🔔 Напоминания")],
        [KeyboardButton("🏦 Накопления"), KeyboardButton("🎯 Мои цели")],
        [KeyboardButton("✏️ Ред. подписку"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("🏆 Достижения"), KeyboardButton("📊 Мультибюджет")],
        [KeyboardButton("💰 Долги/Кредиты"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_currency_keyboard():
    """Валюта кнопкалари"""
    buttons = [[KeyboardButton(c)] for c in CURRENCIES]
    buttons.append([KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_subscription_keyboard():
    """Подписка кнопкалари"""
    buttons = []
    row = []
    for sub in POPULAR_SUBSCRIPTIONS:
        row.append(KeyboardButton(sub))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("✏️ Своё название"), KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def get_category_keyboard():
    """Категория кнопкалари"""
    buttons = [
        [KeyboardButton("🍔 Еда"), KeyboardButton("🚗 Транспорт")],
        [KeyboardButton("🎬 Подписки"), KeyboardButton("🏠 Дом")],
        [KeyboardButton("💊 Здоровье"), KeyboardButton("👕 Одежда")],
        [KeyboardButton("🎮 Развлечения"), KeyboardButton("📚 Образование")],
        [KeyboardButton("📝 Другое"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def get_payment_keyboard():
    """Тўлов усули кнопкалари"""
    buttons = [[KeyboardButton(p)] for p in PAYMENT_METHODS]
    buttons.append([KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def get_back_keyboard():
    """Орқага қайтиш кнопкаси"""
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]], resize_keyboard=True, one_time_keyboard=True)

def get_priority_keyboard():
    """Устуворлик кнопкалари"""
    buttons = [
        [KeyboardButton("🔴 Высокий"), KeyboardButton("🟡 Средний")],
        [KeyboardButton("🟢 Низкий"), KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def get_debt_type_keyboard():
    """Қарз тури кнопкалари"""
    buttons = [
        [KeyboardButton("💰 Я должен"), KeyboardButton("💵 Мне должны")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def get_multi_budget_keyboard(budgets: list):
    """Мультибюджет кнопкалари"""
    buttons = []
    for b in budgets[:8]:
        buttons.append([KeyboardButton(f"📊 {b[1]}: {format_money(b[2], b[3])}")])
    buttons.append([KeyboardButton("➕ Новый бюджет"), KeyboardButton("🔙 Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ========== СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ботни ишга тушириш"""
    db.init_db()
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    # Ютуқларни текшириш
    achievements = db.check_achievements(user_id)
    achievement_msg = ""
    if achievements:
        achievement_msg = f"\n\n🏆 ЯНГИ ЮТУҚ! {', '.join(achievements)}"
    
    await update.message.reply_text(
        f"💰 ФИНАНСОВЫЙ ПОМОЩНИК\n\n"
        f"👋 Привет, {first_name}!\n\n"
        f"📋 Управление подписками\n"
        f"💰 Бюджет и траты\n"
        f"📈 Доходы\n"
        f"🏦 Накопления\n"
        f"🎯 Цели\n"
        f"🤖 Умные советы\n"
        f"🏆 Достижения\n"
        f"📊 Мультибюджет\n"
        f"💰 Долги/Кредиты\n"
        f"📈 Тренды и графики\n\n"
        f"👇 Используйте кнопки!{achievement_msg}",
        reply_markup=get_main_keyboard()
    )

# ========== ПОДПИСКИ ==========
async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фойдаланувчининг подпискаларини кўрсатиш"""
    uid = update.effective_user.id
    subs = db.get_subscriptions(uid)
    currency = db.get_user_currency(uid)
    
    if not subs:
        await update.message.reply_text("📭 *Нет активных подписок*\n\n➕ Добавьте через кнопку", parse_mode="Markdown")
        return
    
    text = "📋 *МОИ ПОДПИСКИ*\n\n"
    total = 0
    for i, s in enumerate(subs, 1):
        sid, name, cost, curr, billing_day, bill_date, is_trial, trial_end, payment, auto_renew, notes = s
        curr = curr or currency
        
        if is_trial and trial_end:
            trial_date = date.fromisoformat(trial_end) if isinstance(trial_end, str) else trial_end
            days = max(0, (trial_date - date.today()).days)
            text += f"🎁 *{i}. {name}* — триал {days} дн.\n"
            text += f"   🗓 До {trial_end}\n"
        else:
            text += f"💸 *{i}. {name}* — {format_money(cost, curr)}/мес\n"
            text += f"   🗓 Списание: {db.format_billing_day(billing_day)}\n"
            text += f"   💳 {payment}, {'🔄 Авто' if auto_renew else '❌ Без автопродления'}\n"
            total += cost
        
        if notes:
            text += f"   📝 {notes[:40]}\n"
        text += "\n"
    
    text += f"💰 *ИТОГО В МЕСЯЦ:* {format_money(total, currency)}\n\n"
    text += f"🗑 Удалить: `/del 1`\n✏️ Редактировать: нажмите '✏️ Ред. подписку'"
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка қўшишни бошлаш"""
    await update.message.reply_text(
        "📝 *ДОБАВЛЕНИЕ ПОДПИСКИ*\n\nВыберите из списка или нажмите '✏️ Своё название':",
        parse_mode="Markdown", reply_markup=get_subscription_keyboard()
    )
    return ADD_SUB_NAME

async def add_sub_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка номини олиш"""
    text = update.message.text
    if text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if text == "✏️ Своё название":
        await update.message.reply_text("📝 *Введите название подписки:*", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SUB_NAME
    
    context.user_data['sub_name'] = text
    await update.message.reply_text("💰 *Стоимость в месяц*\n\n9.99 • 500 000 • 1 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_SUB_COST

async def add_sub_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка нархини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        cost = parse_money(update.message.text)
        if cost <= 0:
            await update.message.reply_text("❌ *Стоимость должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_SUB_COST
        context.user_data['sub_cost'] = cost
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_SUB_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\nПримеры: 9.99 • 500 000 • 1 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SUB_COST

async def add_sub_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['sub_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text(
            "📅 *День списания (1-31)*\n\nВведите число месяца, когда списывают деньги.\nНапример: 5 или 31\n\n💡 Если дня нет в месяце, будет последний день.",
            parse_mode="Markdown", reply_markup=get_back_keyboard()
        )
        return ADD_SUB_DAY
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_SUB_CURRENCY

async def add_sub_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Списание кунини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    is_valid, day, error_msg = db.validate_billing_day(update.message.text)
    if not is_valid:
        await update.message.reply_text(f"{error_msg}\n\n💡 *Примеры:* 5, 15, 31", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SUB_DAY
    
    context.user_data['sub_day'] = day
    kb = [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")], [KeyboardButton("🔙 Назад")]]
    await update.message.reply_text(
        f"🎁 *Это пробный период (триал)?*\n\nДень списания: {db.format_billing_day(day)}",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
    )
    return ADD_SUB_TRIAL

async def add_sub_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Триал борлигини аниқлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if "Да" in update.message.text:
        context.user_data['is_trial'] = True
        await update.message.reply_text(
            "📅 *Дата окончания триала*\n\nФормат: ГГГГ-ММ-ДД\nПример: 2026-06-15\n\n⚠️ После этой даты начнётся платный период!",
            parse_mode="Markdown", reply_markup=get_back_keyboard()
        )
        return ADD_SUB_TRIAL_END
    else:
        context.user_data['is_trial'] = False
        await update.message.reply_text("💳 *Способ оплаты:*", parse_mode="Markdown", reply_markup=get_payment_keyboard())
        return ADD_SUB_PAYMENT

async def add_sub_trial_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Триал тугаш санасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        end_date = date.fromisoformat(update.message.text)
        if end_date <= date.today():
            await update.message.reply_text("❌ *Дата должна быть в будущем!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_SUB_TRIAL_END
        context.user_data['trial_end'] = end_date.isoformat()
        await update.message.reply_text("💳 *Способ оплаты после триала:*", parse_mode="Markdown", reply_markup=get_payment_keyboard())
        return ADD_SUB_PAYMENT
    except:
        await update.message.reply_text("❌ *Неверный формат!*\nИспользуйте: ГГГГ-ММ-ДД\nПример: 2026-06-15", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SUB_TRIAL_END

async def add_sub_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тўлов усулини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['payment_method'] = update.message.text
    kb = [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")], [KeyboardButton("🔙 Назад")]]
    await update.message.reply_text("🔄 *Автоматическое продление?*", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return ADD_SUB_AUTO_RENEW

async def add_sub_auto_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автопродление ҳолатини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['auto_renew'] = "Да" in update.message.text
    await update.message.reply_text("📝 *Заметки (необязательно)*\n\nНапишите заметку или 'пропустить':", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_SUB_NOTES

async def add_sub_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заметкаларни олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    notes = update.message.text if update.message.text.lower() not in ["пропустить", "нет", "-"] else ""
    
    db.add_subscription(
        update.effective_user.id,
        context.user_data['sub_name'],
        context.user_data['sub_cost'],
        context.user_data['sub_day'],
        context.user_data.get('sub_currency', '$'),
        context.user_data.get('is_trial', False),
        context.user_data.get('trial_end'),
        context.user_data.get('payment_method', '💳 Карта'),
        context.user_data.get('auto_renew', True),
        notes
    )
    
    await update.message.reply_text(
        f"✅ *{context.user_data['sub_name']}* добавлена!\n\n"
        f"💰 {format_money(context.user_data['sub_cost'], context.user_data.get('sub_currency', '$'))}/мес\n"
        f"🗓 Списание: {db.format_billing_day(context.user_data['sub_day'])}\n"
        f"💳 {context.user_data.get('payment_method', '💳 Карта')}\n"
        f"🔄 {'Автопродление' if context.user_data.get('auto_renew', True) else 'Без автопродления'}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== БЮДЖЕТ ==========
async def set_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бюджет ўрнатишни бошлаш"""
    cur_b, cur_c, _ = db.get_user(update.effective_user.id)
    msg = f"💰 *Текущий бюджет:* {format_money(cur_b, cur_c)}\n\n*Введите новый бюджет:*\nПример: 500 000" if cur_b > 0 else "💰 *Введите месячный бюджет:*\nПример: 500 000"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_back_keyboard())
    return SET_BUDGET_AMOUNT

async def set_budget_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бюджет миқдорини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        budget = parse_money(update.message.text)
        if budget <= 0:
            await update.message.reply_text("❌ *Бюджет должен быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return SET_BUDGET_AMOUNT
        context.user_data['budget_amount'] = budget
        await update.message.reply_text("💱 *Выберите валюту бюджета:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return SET_BUDGET_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\nПример: 500 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return SET_BUDGET_AMOUNT

async def set_budget_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бюджет валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        cur = CURRENCY_SYMBOLS[update.message.text]
        db.set_user_budget(update.effective_user.id, context.user_data['budget_amount'], cur)
        await update.message.reply_text(f"✅ *Бюджет установлен!*\n💰 {format_money(context.user_data['budget_amount'], cur)}", parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return SET_BUDGET_CURRENCY
    return ConversationHandler.END

# ========== ТРАТЫ ==========
async def add_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата қўшишни бошлаш"""
    await update.message.reply_text("💸 *Сумма траты*\n\n5.50 • 50 000 • 1 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата суммасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = parse_money(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_EXPENSE_AMOUNT
        context.user_data['expense_amount'] = amount
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_EXPENSE_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n5.50 • 50 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_EXPENSE_AMOUNT

async def add_expense_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['expense_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text("📂 *Выберите категорию:*", parse_mode="Markdown", reply_markup=get_category_keyboard())
        return ADD_EXPENSE_CATEGORY
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_EXPENSE_CURRENCY

async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата категориясини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['expense_cat'] = EXPENSE_CATEGORIES.get(update.message.text, "Другое")
    await update.message.reply_text("📝 *Описание* (или 'пропустить'):", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_EXPENSE_DESC

async def add_expense_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата тавсифини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    desc_text = update.message.text if update.message.text.lower() != "пропустить" else ""
    context.user_data['expense_desc'] = desc_text
    await update.message.reply_text("🏷 *Теги* (через запятую или 'пропустить'):\nкофе, встреча, срочно", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_EXPENSE_TAGS

async def add_expense_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Трата тегларини олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    tags = update.message.text if update.message.text.lower() not in ["пропустить", "нет", "-"] else ""
    
    db.add_expense(
        update.effective_user.id,
        context.user_data['expense_amount'],
        context.user_data['expense_cat'],
        context.user_data.get('expense_desc', ''),
        context.user_data.get('expense_currency', '$'),
        tags
    )
    
    # Ютуқларни текшириш
    achievements = db.check_achievements(update.effective_user.id)
    achievement_msg = ""
    if achievements:
        achievement_msg = f"\n\n🏆 *ЮТУҚ!* {', '.join(achievements)}"
    
    await update.message.reply_text(
        f"✅ *Трата добавлена!*\n\n"
        f"💰 {format_money(context.user_data['expense_amount'], context.user_data.get('expense_currency', '$'))}\n"
        f"📂 {context.user_data['expense_cat']}\n"
        f"🏷 {tags if tags else '—'}{achievement_msg}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== ДОХОДЫ ==========
async def add_income_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Доход қўшишни бошлаш"""
    await update.message.reply_text("📈 *Сумма дохода*\n\n500 000 • 1 000 • 50", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_INCOME_AMOUNT

async def add_income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Доход суммасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = parse_money(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_INCOME_AMOUNT
        context.user_data['income_amount'] = amount
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_INCOME_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n500 000 • 1 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_INCOME_AMOUNT

async def add_income_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Доход валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['income_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text("📝 *Источник дохода:*\nЗарплата, Фриланс, Подарок", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_INCOME_SOURCE
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_INCOME_CURRENCY

async def add_income_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Доход манбасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['income_source'] = update.message.text if update.message.text.lower() not in ["пропустить", "нет", "-"] else "Другое"
    
    # Авто-цель таклифи
    income_amount = context.user_data['income_amount']
    recommended_saving = income_amount * 0.2
    currency = context.user_data.get('income_currency', '$')
    
    kb = [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")], [KeyboardButton("🔙 Назад")]]
    
    await update.message.reply_text(
        f"📈 *Доход:* {format_money(income_amount, currency)}\n\n"
        f"💡 *Совет:* Рекомендую отложить 20% = {format_money(recommended_saving, currency)} на накопления!\n\n"
        f"🔄 *Регулярный доход?* (каждый месяц)",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
    )
    return ADD_INCOME_RECURRING

async def add_income_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Доходни сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    is_recurring = "Да" in update.message.text
    
    db.add_income(
        update.effective_user.id,
        context.user_data['income_amount'],
        context.user_data.get('income_currency', '$'),
        context.user_data.get('income_source', 'Другое'),
        is_recurring
    )
    
    await update.message.reply_text(
        f"✅ *Доход добавлен!*\n\n"
        f"💰 {format_money(context.user_data['income_amount'], context.user_data.get('income_currency', '$'))}\n"
        f"📝 {context.user_data.get('income_source', 'Другое')}\n"
        f"🔄 {'Регулярный' if is_recurring else 'Разовый'}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== СТАТИСТИКА С ГРАФИКОМ (Функция 1) ==========
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистикани график билан кўрсатиш"""
    uid = update.effective_user.id
    budget, cur, _ = db.get_user(uid)
    subs_total = db.get_total_monthly_cost(uid)
    expenses = db.get_total_expenses_last_days(uid, 30)
    incomes = db.get_total_incomes_last_days(uid, 30)
    by_cat = db.get_expenses_by_category(uid, 30)
    daily = db.get_daily_expenses(uid, 30)
    
    text = f"📊 *СТАТИСТИКА (30 дней)*\n\n"
    text += f"💰 *Бюджет:* {format_money(budget, cur)}\n"
    text += f"📈 *Доход:* {format_money(incomes, cur)}\n"
    text += f"💸 *Расход:* {format_money(expenses, cur)}\n"
    text += f"📆 *Подписки:* {format_money(subs_total, cur)}/мес\n"
    text += f"💵 *Баланс:* {format_money(incomes - expenses, cur)}\n\n"
    
    if budget > 0:
        remaining = budget - expenses
        percent = (expenses / budget) * 100 if budget > 0 else 0
        text += f"✅ *Остаток:* {format_money(remaining, cur)}\n"
        text += f"📊 *Выполнено:* {percent:.0f}%\n"
        bar = "█" * min(int(percent/10), 10) + "░" * (10 - min(int(percent/10), 10))
        text += f"📈 {bar} {percent:.0f}%\n\n"
        free = remaining - subs_total
        if free > 0:
            text += f"💸 *Свободно:* {format_money(free, cur)}\n"
        else:
            text += f"⚠️ *Подписки превышают остаток!*\n"
    
    # Категориялар бўйича статистика
    text += f"\n📂 *РАСХОДЫ ПО КАТЕГОРИЯМ:*\n"
    if by_cat:
        for cat, data in sorted(by_cat.items(), key=lambda x: x[1]['amount'], reverse=True)[:5]:
            percent = (data['amount'] / expenses * 100) if expenses > 0 else 0
            bar = "▰" * min(int(percent/5), 20) + "▱" * (20 - min(int(percent/5), 20))
            text += f"• {cat}: {format_money(data['amount'], cur)} {bar} {percent:.0f}% ({data['count']} раз)\n"
    else:
        text += "• Нет трат\n"
    
    # Трендлар (Функция 7)
    text += await show_trends(update, context)
    
    if daily:
        avg = expenses / len(daily)
        text += f"\n📅 *Среднее в день:* {format_money(avg, cur)}\n"
    
    if expenses > incomes and incomes > 0:
        text += f"\n⚠️ *Вы тратите больше, чем зарабатываете!*"
    
    await update.message.reply_text(text, parse_mode="Markdown")
    
    # Pie chart юбориш (Функция 1 - график расм)
    await send_pie_chart(update, context)

async def send_pie_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pie chart расмини юбориш"""
    uid = update.effective_user.id
    by_cat = db.get_expenses_by_category(uid, 30)
    
    if not by_cat:
        await update.message.reply_text("📊 *Нет данных для графика*", parse_mode="Markdown")
        return
    
    # Matplotlib да график яратиш
    fig, ax = plt.subplots(figsize=(10, 8))
    
    categories = list(by_cat.keys())
    amounts = [data['amount'] for data in by_cat.values()]
    
    # Ранглар
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dfe6e9', '#fdcb6e', '#e17055', '#74b9ff']
    
    wedges, texts, autotexts = ax.pie(amounts, labels=categories, autopct='%1.1f%%',
                                        colors=colors[:len(categories)], startangle=90)
    ax.set_title('📊 Расходы по категориям (30 дней)', fontsize=14, fontweight='bold')
    
    # Форматлаш
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_fontweight('bold')
    
    # Расмни сақлаш
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    
    await update.message.reply_photo(photo=buf, caption="📊 *Диаграмма расходов по категориям*", parse_mode="Markdown")

# ========== ТРЕНДЛАР (Функция 7) ==========
async def show_trends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Трендларни кўрсатиш (ўсиш/пасайиш)"""
    uid = update.effective_user.id
    
    # Охирги 30 кунлик харажатлар
    expenses_30 = db.get_total_expenses_last_days(uid, 30)
    
    # Охирги 60 кунлик харажатлар
    expenses_60 = db.get_total_expenses_last_days(uid, 60)
    
    if expenses_60 == 0:
        return ""
    
    # Трендни ҳисоблаш
    expenses_prev = expenses_60 - expenses_30
    if expenses_prev > 0:
        change = ((expenses_30 - expenses_prev) / expenses_prev) * 100
        if change > 5:
            return f"\n📈 *ТРЕНД:* Расходы выросли на {change:.1f}% по сравнению с предыдущим месяцем! ⚠️"
        elif change < -5:
            return f"\n📉 *ТРЕНД:* Расходы снизились на {abs(change):.1f}%! ✅ Отлично!"
        else:
            return f"\n📊 *ТРЕНД:* Расходы стабильны (изменение {change:.1f}%)"
    return ""

# ========== SMART-НАПОМИНАНИЯ (Функция 2) ==========
async def reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart-напоминания: 7, 3, 1 кун олдин эслатма"""
    uid = update.effective_user.id
    cur = db.get_user_currency(uid)
    
    # 7 кунлик эслатмалар
    upcoming_7 = db.get_upcoming_billing(uid, 7)
    # 3 кунлик эслатмалар
    upcoming_3 = db.get_upcoming_billing(uid, 3)
    # 1 кунлик эслатмалар
    upcoming_1 = db.get_upcoming_billing(uid, 1)
    
    if not upcoming_7:
        await update.message.reply_text("🔔 *Нет ближайших списаний*\n\n✅ Отдыхайте спокойно!", parse_mode="Markdown")
        return
    
    text = "🔔 *SMART-НАПОМИНАНИЯ*\n\n"
    
    # 1 кун қолганлар (энг муҳим)
    if upcoming_1:
        text += "🚨 *СРОЧНО! СПИСАНИЕ ЗАВТРА:*\n"
        for sub_id, name, cost, curr, due_date, is_trial in upcoming_1:
            curr = curr or cur
            if is_trial:
                text += f"   🎁 {name} — триал ДО {due_date.strftime('%d.%m.%Y')}!\n"
            else:
                text += f"   💸 {name} — {format_money(cost, curr)} • {due_date.strftime('%d.%m.%Y')}\n"
        text += "\n"
    
    # 3 кун қолганлар
    if upcoming_3:
        text += "⏰ *ЧЕРЕЗ 3 ДНЯ:*\n"
        for sub_id, name, cost, curr, due_date, is_trial in upcoming_3:
            curr = curr or cur
            if is_trial:
                text += f"   🎁 {name} — триал ДО {due_date.strftime('%d.%m.%Y')}\n"
            else:
                text += f"   💸 {name} — {format_money(cost, curr)} • {due_date.strftime('%d.%m.%Y')}\n"
        text += "\n"
    
    # 7 кун қолганлар
    if upcoming_7:
        text += "📅 *ЧЕРЕЗ 7 ДНЕЙ:*\n"
        for sub_id, name, cost, curr, due_date, is_trial in upcoming_7:
            curr = curr or cur
            if is_trial:
                continue  # 7 кунликларда триалларни кўрсатмасак ҳам бўлади
            else:
                text += f"   💸 {name} — {format_money(cost, curr)} • {due_date.strftime('%d.%m.%Y')}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== ДОЛГИ/КРЕДИТЫ (Функция 3) - ИСПРАВЛЕНО ==========
async def debts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарзлар менюси"""
    uid = update.effective_user.id
    debts = db.get_debts(uid)
    currency = db.get_user_currency(uid)
    
    if not debts:
        await update.message.reply_text(
            "💰 *ДОЛГИ/КРЕДИТЫ*\n\n"
            "Нет долгов.\n\n"
            "➕ Добавить долг: нажмите кнопку 'Добавить долг' ниже\n\n"
            "📝 Краткий отчёт о долгах будет показан здесь.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("➕ Добавить долг"), KeyboardButton("🔙 Назад")]],
                resize_keyboard=True
            )
        )
        return
    
    text = "💰 *ПОЛНЫЙ УЧЁТ ДОЛГОВ*\n\n"
    
    # Қарзларим (мен олишим керак)
    my_debts = [d for d in debts if d[7] == 'owed_to_me']
    if my_debts:
        text += "📥 *МНЕ ДОЛЖНЫ:*\n"
        total_owed = 0
        for idx, d in enumerate(my_debts, 1):
            did, uid, name, amount, curr, who, debt_date, dtype, notes = d
            curr = curr or currency
            text += f"   {idx}. {name}: {format_money(amount, curr)} — {who}\n"
            if notes:
                text += f"     📝 {notes}\n"
            total_owed += amount
        text += f"   💰 *ИТОГО:* {format_money(total_owed, currency)}\n\n"
    
    # Менинг қарзларим (мен тўлашим керак)
    i_owe = [d for d in debts if d[7] == 'i_owe']
    if i_owe:
        text += "📤 *Я ДОЛЖЕН:*\n"
        total_owe = 0
        for idx, d in enumerate(i_owe, 1):
            did, uid, name, amount, curr, who, debt_date, dtype, notes = d
            curr = curr or currency
            text += f"   {idx}. {name}: {format_money(amount, curr)} — {who}\n"
            if notes:
                text += f"     📝 {notes}\n"
            total_owe += amount
        text += f"   💰 *ИТОГО:* {format_money(total_owe, currency)}\n\n"
    
    text += "💡 *Управление:*\n"
    text += "• Удалить: `/del_debt 1`\n"
    text += "• Отметить как оплачено: `/pay_debt 1`"
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(
        [[KeyboardButton("➕ Добавить долг"), KeyboardButton("🔙 Назад")]],
        resize_keyboard=True
    ))

async def add_debt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарз қўшишни бошлаш"""
    await update.message.reply_text(
        "💰 *ДОБАВЛЕНИЕ ДОЛГА*\n\n"
        "Выберите тип долга:",
        parse_mode="Markdown", reply_markup=get_debt_type_keyboard()
    )
    return ADD_DEBT_TYPE

async def add_debt_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарз турини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text == "💰 Я должен":
        context.user_data['debt_type'] = 'i_owe'
        await update.message.reply_text("📝 *Что должны?*\nНапример: за телефон, за еду", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_DEBT_NAME
    elif update.message.text == "💵 Мне должны":
        context.user_data['debt_type'] = 'owed_to_me'
        await update.message.reply_text("📝 *Что должны вам?*\nНапример: за работу, за товар", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_DEBT_NAME
    else:
        await update.message.reply_text("❌ Выберите тип долга из кнопок!", reply_markup=get_debt_type_keyboard())
        return ADD_DEBT_TYPE

async def add_debt_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарз номини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['debt_name'] = update.message.text
    await update.message.reply_text("💰 *Сумма долга:*\n50000 • 100000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_DEBT_AMOUNT

async def add_debt_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарз миқдорини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = parse_money(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_DEBT_AMOUNT
        context.user_data['debt_amount'] = amount
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_DEBT_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n50000 • 100000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_DEBT_AMOUNT

async def add_debt_currency_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарз валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['debt_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text("👤 *Кто?*\n(Имя человека)", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_DEBT_WHO
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_DEBT_CURRENCY

async def add_debt_who_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кимлигини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['debt_who'] = update.message.text
    await update.message.reply_text("📅 *Дата долга (ГГГГ-ММ-ДД)*\nИли 'сегодня':", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_DEBT_WHEN

async def add_debt_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қарзни сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text.lower() == 'сегодня':
        debt_date = date.today().isoformat()
    else:
        try:
            debt_date = date.fromisoformat(update.message.text).isoformat()
        except:
            debt_date = date.today().isoformat()
    
    db.add_debt(
        update.effective_user.id,
        context.user_data['debt_name'],
        context.user_data['debt_amount'],
        context.user_data.get('debt_currency', '$'),
        context.user_data['debt_who'],
        debt_date,
        context.user_data['debt_type']
    )
    
    debt_type_text = "Я должен" if context.user_data['debt_type'] == 'i_owe' else "Мне должны"
    await update.message.reply_text(
        f"✅ *Долг добавлен!*\n\n"
        f"📝 {debt_type_text}: {context.user_data['debt_name']}\n"
        f"💰 {format_money(context.user_data['debt_amount'], context.user_data.get('debt_currency', '$'))}\n"
        f"👤 {context.user_data['debt_who']}\n"
        f"📅 {debt_date}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== МУЛЬТИБЮДЖЕТ (Функция 4) ==========
async def multi_budget_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мультибюджет менюси"""
    uid = update.effective_user.id
    budgets = db.get_multiple_budgets(uid)
    currency = db.get_user_currency(uid)
    
    if not budgets:
        await update.message.reply_text(
            "📊 *МУЛЬТИБЮДЖЕТ*\n\n"
            "У вас нет отдельных бюджетов.\n\n"
            "➕ Нажмите 'Новый бюджет' чтобы создать бюджет для конкретной цели:\n"
            "• Еда\n"
            "• Транспорт\n"
            "• Развлечения\n"
            "• И т.д.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("➕ Новый бюджет"), KeyboardButton("🔙 Назад")]], 
                resize_keyboard=True
            )
        )
        return
    
    text = "📊 *АЛОҲИДА БЮДЖЕТЛАР*\n\n"
    total_budget = 0
    total_spent = 0
    
    for b in budgets:
        bid, uid, name, amount, currency_b, spent, created = b
        currency_b = currency_b or currency
        remaining = amount - spent
        percent = (spent / amount * 100) if amount > 0 else 0
        
        text += f"📌 *{name}*\n"
        text += f"   💰 Бюджет: {format_money(amount, currency_b)}\n"
        text += f"   💸 Потрачено: {format_money(spent, currency_b)}\n"
        text += f"   ✅ Остаток: {format_money(remaining, currency_b)}\n"
        
        bar = "█" * min(int(percent/10), 10) + "░" * (10 - min(int(percent/10), 10))
        text += f"   📊 {bar} {percent:.0f}%\n\n"
        
        total_budget += amount
        total_spent += spent
    
    text += f"📊 *ИТОГО:*\n"
    text += f"   📋 Всего бюджет: {format_money(total_budget, currency)}\n"
    text += f"   💸 Всего потрачено: {format_money(total_spent, currency)}\n"
    text += f"   ✅ Остаток: {format_money(total_budget - total_spent, currency)}\n\n"
    
    text += "📝 Для добавления траты в конкретный бюджет, используйте кнопку '💸 Добавить трату' и укажите бюджет."
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_multi_budget_keyboard(budgets))

async def add_multi_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мультибюджет қўшишни бошлаш"""
    if update.message.text == "➕ Новый бюджет":
        await update.message.reply_text(
            "📊 *НОВЫЙ БЮДЖЕТ*\n\n"
            "Введите название бюджета:\n"
            "• Еда\n"
            "• Транспорт\n"
            "• Развлечения\n"
            "• Одежда\n"
            "• И т.д.",
            parse_mode="Markdown", reply_markup=get_back_keyboard()
        )
        return ADD_MULTI_BUDGET_NAME
    else:
        await multi_budget_menu(update, context)
        return ConversationHandler.END

async def add_multi_budget_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мультибюджет номини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['multi_budget_name'] = update.message.text
    await update.message.reply_text("💰 *Сумма бюджета:*\n500000 • 1000000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_MULTI_BUDGET_AMOUNT

async def add_multi_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мультибюджет суммасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = parse_money(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_MULTI_BUDGET_AMOUNT
        context.user_data['multi_budget_amount'] = amount
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_MULTI_BUDGET_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n500000 • 1000000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_MULTI_BUDGET_AMOUNT

async def add_multi_budget_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мультибюджет валютсини олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        cur = CURRENCY_SYMBOLS[update.message.text]
        db.add_multiple_budget(
            update.effective_user.id,
            context.user_data['multi_budget_name'],
            context.user_data['multi_budget_amount'],
            cur
        )
        await update.message.reply_text(
            f"✅ *Бюджет создан!*\n\n"
            f"📌 {context.user_data['multi_budget_name']}\n"
            f"💰 {format_money(context.user_data['multi_budget_amount'], cur)}",
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_MULTI_BUDGET_CURRENCY
    
    return ConversationHandler.END

# ========== ДОСТИЖЕНИЯ (Функция 6) ==========
async def achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ютуқларни кўрсатиш (10, 50, 100 трат)"""
    uid = update.effective_user.id
    total_expenses = len(db.get_expenses(uid, 9999))
    achievements_data = db.get_achievements(uid)
    
    text = "🏆 *ДОСТИЖЕНИЯ*\n\n"
    text += f"📊 Всего трат: *{total_expenses}*\n\n"
    
    achievements = {
        'first_expense': '🎉 Первая трата',
        '10_expenses': '📊 10 трат',
        '50_expenses': '🔥 50 трат', 
        '100_expenses': '🏆 100 трат',
        'budget_saver': '💰 Экономия бюджета',
        'subscription_killer': '🗑 Удалено 5 подписок'
    }
    
    for key, name in achievements.items():
        if key in achievements_data:
            text += f"✅ {name} — *получено*\n"
        else:
            text += f"❌ {name} — *не получено*\n"
    
    if total_expenses >= 100:
        text += "\n🌟 *ВЫ — МАСТЕР ФИНАНСОВ!* 🌟"
    elif total_expenses >= 50:
        text += "\n⭐ *Осталось 50 трат до 100!*"
    elif total_expenses >= 10:
        text += "\n📈 *Хороший прогресс! Осталось 40 трат до 50!*"
    else:
        text += f"\n🎯 *До 10 трат осталось: {10 - total_expenses}*"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== НАКОПЛЕНИЯ ==========
async def add_saving_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Накопление қўшишни бошлаш"""
    await update.message.reply_text("🏦 *Сколько откладываете?*\n50 000 • 100 • 1 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_SAVING_AMOUNT

async def add_saving_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Накопление суммасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        saving = parse_money(update.message.text)
        if saving <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_SAVING_AMOUNT
        context.user_data['saving_amount'] = saving
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_SAVING_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n50 000 • 100", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SAVING_AMOUNT

async def add_saving_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Накопление валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['saving_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text("🏷 *Цель накопления* (или 'пропустить'):\nНовая машина • Квартира • Отпуск", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_SAVING_PURPOSE
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_SAVING_CURRENCY

async def add_saving_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Накопление мақсадини олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    purpose = update.message.text if update.message.text.lower() not in ["пропустить", "нет", "-"] else "Накопления"
    
    total = db.add_saving(
        update.effective_user.id,
        context.user_data['saving_amount'],
        context.user_data.get('saving_currency', '$'),
        purpose
    )
    
    await update.message.reply_text(
        f"🏦 *Отложено!*\n\n"
        f"💰 {format_money(context.user_data['saving_amount'], context.user_data.get('saving_currency', '$'))}\n"
        f"🏷 {purpose if purpose else 'Без цели'}\n"
        f"📊 *Всего накоплено:* {format_money(total, context.user_data.get('saving_currency', '$'))}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== ЦЕЛИ ==========
async def add_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад қўшишни бошлаш"""
    await update.message.reply_text("🎯 *Название цели*\nНовая машина, Квартира, Путешествие", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_GOAL_NAME

async def add_goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад номини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['goal_name'] = update.message.text
    await update.message.reply_text("💰 *Сумма цели*\n10 000 000 • 500 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    return ADD_GOAL_AMOUNT

async def add_goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад суммасини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = parse_money(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ *Сумма должна быть больше 0!*", parse_mode="Markdown", reply_markup=get_back_keyboard())
            return ADD_GOAL_AMOUNT
        context.user_data['goal_amount'] = amount
        await update.message.reply_text("💱 *Выберите валюту:*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_GOAL_CURRENCY
    except:
        await update.message.reply_text("❌ *Ошибка!*\n10 000 000 • 500 000", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_GOAL_AMOUNT

async def add_goal_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад валютсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if update.message.text in CURRENCIES:
        context.user_data['goal_currency'] = CURRENCY_SYMBOLS[update.message.text]
        await update.message.reply_text("📅 *Дедлайн* (ГГГГ-ММ-ДД) или 'пропустить':\n2026-12-31", parse_mode="Markdown", reply_markup=get_back_keyboard())
        return ADD_GOAL_DEADLINE
    else:
        await update.message.reply_text("❌ *Выберите валюту из кнопок!*", parse_mode="Markdown", reply_markup=get_currency_keyboard())
        return ADD_GOAL_CURRENCY

async def add_goal_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад дедлайнини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    deadline = None
    if update.message.text.lower() not in ["пропустить", "нет", "-"]:
        try:
            deadline = update.message.text
        except:
            deadline = None
    
    await update.message.reply_text("⚡ *Приоритет цели:*", parse_mode="Markdown", reply_markup=get_priority_keyboard())
    return ADD_GOAL_PRIORITY

async def add_goal_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мақсад устуворлигини олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    priority_map = {"🔴 Высокий": 3, "🟡 Средний": 2, "🟢 Низкий": 1}
    priority = priority_map.get(update.message.text, 2)
    
    db.add_goal(
        update.effective_user.id,
        context.user_data['goal_name'],
        context.user_data['goal_amount'],
        context.user_data.get('goal_currency', '$'),
        context.user_data.get('goal_deadline'),
        priority
    )
    
    await update.message.reply_text(
        f"🎯 *Цель установлена!*\n\n"
        f"📌 {context.user_data['goal_name']}\n"
        f"💰 {format_money(context.user_data['goal_amount'], context.user_data.get('goal_currency', '$'))}",
        parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ========== РЕДАКТИРОВАНИЕ ПОДПИСКИ ==========
async def edit_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подпискани таҳрирлашни бошлаш"""
    uid = update.effective_user.id
    subs = db.get_subscriptions(uid)
    if not subs:
        await update.message.reply_text("📭 *Нет подписок для редактирования*", parse_mode="Markdown")
        return
    
    text = "✏️ *РЕДАКТИРОВАНИЕ ПОДПИСКИ*\n\nВведите номер подписки:\n"
    for i, s in enumerate(subs, 1):
        text += f"{i}. {s[1]} — {format_money(s[2], s[3] or db.get_user_currency(uid))}/мес\n"
    text += "\n💡 Например: *1*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_back_keyboard())
    return EDIT_SUBSCRIPTION_ID

async def edit_subscription_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка IDсини олиш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        num = int(update.message.text)
        uid = update.effective_user.id
        subs = db.get_subscriptions(uid)
        if 1 <= num <= len(subs):
            context.user_data['edit_sub_id'] = subs[num-1][0]
            context.user_data['edit_sub_name'] = subs[num-1][1]
            
            text = f"✏️ *Редактируем:* {subs[num-1][1]}\n\nЧто изменить?\n• цена\n• день списания\n• способ оплаты\n• автопродление\n• заметки\n\nНапишите: *цена 9.99* или *день 15*"
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_back_keyboard())
            return EDIT_SUBSCRIPTION_FIELD
        else:
            await update.message.reply_text(f"❌ Подписка #{num} не найдена", parse_mode="Markdown")
            return EDIT_SUBSCRIPTION_ID
    except:
        await update.message.reply_text("❌ *Ошибка!* Введите номер подписки", parse_mode="Markdown")
        return EDIT_SUBSCRIPTION_ID

async def edit_subscription_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Қайси майдонни таҳрирлашни аниқлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    msg = update.message.text.lower()
    if "цена" in msg or "cost" in msg:
        context.user_data['edit_field'] = 'cost'
        await update.message.reply_text("💰 *Новая стоимость:*\n9.99 или 500000", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif "день" in msg or "day" in msg or "списание" in msg:
        context.user_data['edit_field'] = 'billing_day'
        await update.message.reply_text("📅 *Новый день списания (1-31):*", parse_mode="Markdown", reply_markup=get_back_keyboard())
    elif "оплат" in msg or "payment" in msg:
        context.user_data['edit_field'] = 'payment_method'
        await update.message.reply_text("💳 *Новый способ оплаты:*", parse_mode="Markdown", reply_markup=get_payment_keyboard())
    elif "авто" in msg or "auto" in msg:
        context.user_data['edit_field'] = 'auto_renew'
        kb = [[KeyboardButton("✅ Да"), KeyboardButton("❌ Нет")], [KeyboardButton("🔙 Назад")]]
        await update.message.reply_text("🔄 *Включить автопродление?*", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    elif "заметк" in msg or "note" in msg:
        context.user_data['edit_field'] = 'notes'
        await update.message.reply_text("📝 *Новая заметка:*", parse_mode="Markdown", reply_markup=get_back_keyboard())
    else:
        await update.message.reply_text("❌ *Что изменить?*\nцена 9.99 • день 15 • оплата Карта", parse_mode="Markdown")
        return EDIT_SUBSCRIPTION_FIELD
    
    return EDIT_SUBSCRIPTION_VALUE

async def edit_subscription_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Янги қийматни олиш ва сақлаш"""
    if update.message.text == "🔙 Назад":
        await update.message.reply_text("❌ Отмена", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    field = context.user_data.get('edit_field')
    value = update.message.text
    
    updates = {}
    if field == 'cost':
        try:
            updates['cost'] = parse_money(value)
            await update.message.reply_text(f"✅ *Стоимость изменена* на {format_money(updates['cost'], '$')}", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ *Ошибка!* 9.99", parse_mode="Markdown")
            return EDIT_SUBSCRIPTION_VALUE
    elif field == 'billing_day':
        is_valid, day, error = db.validate_billing_day(value)
        if is_valid:
            updates['billing_day'] = day
            await update.message.reply_text(f"✅ *День списания изменён* на {db.format_billing_day(day)}", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {error}", parse_mode="Markdown")
            return EDIT_SUBSCRIPTION_VALUE
    elif field == 'payment_method':
        updates['payment_method'] = value
        await update.message.reply_text(f"✅ *Способ оплаты изменён* на {value}", parse_mode="Markdown")
    elif field == 'auto_renew':
        updates['auto_renew'] = "Да" in value
        await update.message.reply_text(f"✅ *Автопродление* {'включено' if updates['auto_renew'] else 'выключено'}", parse_mode="Markdown")
    elif field == 'notes':
        updates['notes'] = value if value.lower() not in ["пропустить", "нет", "-"] else ""
        await update.message.reply_text(f"✅ *Заметки сохранены*", parse_mode="Markdown")
    
    if updates:
        db.update_subscription(context.user_data['edit_sub_id'], update.effective_user.id, **updates)
        await update.message.reply_text(f"✅ *{context.user_data['edit_sub_name']}* обновлена!", parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("❌ *Ничего не изменено*", reply_markup=get_main_keyboard())
    
    return ConversationHandler.END

# ========== AI ПОМОЩНИК С КОНТЕКСТОМ (Функция 9) ==========
async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI чат режими (контекст билан)"""
    await update.message.reply_text(
        "🤖 *AI ПОМОЩНИК С КОНТЕКСТОМ*\n\n"
        "Задайте любой вопрос, я запоминаю предыдущие вопросы!\n\n"
        "💡 Примеры:\n"
        "• Как сэкономить на еде?\n"
        "• Какие подписки отключить?\n"
        "• Как вести бюджет?\n"
        "• Что такое мультибюджет?\n"
        "• Как правильно копить деньги?\n\n"
        "❌ 'выход' - выйти из режима",
        parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
    context.user_data['ai_mode'] = True
    context.user_data['ai_context'] = []  # Контекст учун сақлаш

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI саволларга жавоб бериш"""
    if context.user_data.get('ai_mode'):
        msg = update.message.text
        if msg.lower() in ['выход', 'стоп', 'exit', 'quit', '🔙 назад']:
            context.user_data['ai_mode'] = False
            context.user_data['ai_context'] = []
            await update.message.reply_text("👋 Выход из AI чата", reply_markup=get_main_keyboard())
            return
        
        uid = update.effective_user.id
        budget, cur, _ = db.get_user(uid)
        budget_info = f"Бюджет: {format_money(budget, cur)}. " if budget > 0 else ""
        
        # Контекстни сақлаш
        context.user_data['ai_context'].append(msg)
        if len(context.user_data['ai_context']) > 5:
            context.user_data['ai_context'] = context.user_data['ai_context'][-5:]
        
        answer = ai_response(msg, budget_info, context.user_data['ai_context'])
        
        # Контекстни кўрсатиш
        if len(context.user_data['ai_context']) > 1:
            answer += f"\n\n💬 (Я помню предыдущий вопрос: '{context.user_data['ai_context'][-2][:50]}...')"
        
        await update.message.reply_text(f"🤖 {answer}")
        return True
    return False

# ========== НАСТРОЙКИ ==========
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройкалар менюси"""
    uid = update.effective_user.id
    budget, cur, _ = db.get_user(uid)
    subs_count = len(db.get_subscriptions(uid))
    savings = db.get_total_savings(uid, cur)
    incomes_total = db.get_total_incomes_last_days(uid, 30)
    expenses_total = db.get_total_expenses_last_days(uid, 30)
    debt_summary = db.get_debt_summary(uid)
    debts = debt_summary['owed_to_me'] + debt_summary['i_owe']
    
    text = f"⚙️ *НАСТРОЙКИ*\n\n"
    text += f"💰 Бюджет: {format_money(budget, cur)}\n"
    text += f"💱 Валюта: {cur}\n"
    text += f"📋 Подписок: {subs_count}\n"
    text += f"🏦 Накоплено: {format_money(savings, cur)}\n"
    text += f"💸 Всего долгов: {format_money(debts, cur)}\n"
    text += f"📈 Доход (мес): {format_money(incomes_total, cur)}\n"
    text += f"💸 Расход (мес): {format_money(expenses_total, cur)}\n"
    text += f"📊 Экономия: {format_money(incomes_total - expenses_total, cur)}\n\n"
    text += f"📌 Сменить валюту → '💰 Бюджет'\n"
    text += f"💬 Чат с AI → '🤖 AI Помощник'"
    await update.message.reply_text(text, parse_mode="Markdown")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асосий менюга қайтиш"""
    context.user_data.clear()
    await update.message.reply_text("🔙 *Главное меню*", parse_mode="Markdown", reply_markup=get_main_keyboard())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Диалогни бекор қилиш"""
    context.user_data.clear()
    await update.message.reply_text("❌ *Отмена*", parse_mode="Markdown", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подпискани ўчириш"""
    if update.message.text.startswith("/del"):
        try:
            num = int(update.message.text.split()[1])
            subs = db.get_subscriptions(update.effective_user.id)
            if 1 <= num <= len(subs):
                db.delete_subscription(subs[num-1][0], update.effective_user.id)
                
                # Ютуқларни текшириш
                achievements = db.check_achievements(update.effective_user.id)
                achievement_msg = ""
                if achievements:
                    achievement_msg = f"\n\n🏆 *ЮТУҚ!* {', '.join(achievements)}"
                
                await update.message.reply_text(f"🗑 *Удалено:* {subs[num-1][1]}{achievement_msg}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Подписка #{num} не найдена", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ *Используйте:* `/del 1`", parse_mode="Markdown")
    elif update.message.text.startswith("/del_debt"):
        try:
            num = int(update.message.text.split()[1])
            debts = db.get_debts(update.effective_user.id)
            if 1 <= num <= len(debts):
                db.delete_debt(debts[num-1][0], update.effective_user.id)
                await update.message.reply_text(f"🗑 *Долг удалён:* {debts[num-1][2]}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Долг #{num} не найден", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ *Используйте:* `/del_debt 1`", parse_mode="Markdown")
    elif update.message.text.startswith("/pay_debt"):
        try:
            num = int(update.message.text.split()[1])
            debts = db.get_debts(update.effective_user.id)
            if 1 <= num <= len(debts):
                db.pay_debt(debts[num-1][0], update.effective_user.id)

                # Ютуқларни текшириш
                achievements = db.check_achievements(update.effective_user.id)
                achievement_msg = ""
                if achievements:
                    achievement_msg = f"\n\n🏆 *ЮТУҚ!* {', '.join(achievements)}"

                await update.message.reply_text(f"✅ *Долг отмечен как оплаченный:* {debts[num-1][2]}{achievement_msg}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Долг #{num} не найден", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ *Используйте:* `/pay_debt 1`", parse_mode="Markdown")

async def add_debt_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка добавления долга"""
    if update.message.text == "➕ Добавить долг":
        await add_debt_start(update, context)
    else:
        await debts_menu(update, context)

# ========== ОБРАБОТЧИКИ ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопкаларни қайта ишлаш"""
    t = update.message.text
    
    if t == "📋 Мои подписки":
        await my_subscriptions(update, context)
    elif t == "➕ Добавить подписку":
        await add_subscription_start(update, context)
    elif t == "💰 Бюджет":
        await set_budget_start(update, context)
    elif t == "💸 Добавить трату":
        await add_expense_start(update, context)
    elif t == "📈 Добавить доход":
        await add_income_start(update, context)
    elif t == "📊 Статистика":
        await show_stats(update, context)
    elif t == "🤖 AI Помощник":
        await ai_chat_mode(update, context)
    elif t == "🔔 Напоминания":
        await reminders_menu(update, context)
    elif t == "🏦 Накопления":
        await add_saving_start(update, context)
    elif t == "🎯 Мои цели":
        await add_goal_start(update, context)
    elif t == "✏️ Ред. подписку":
        await edit_subscription_start(update, context)
    elif t == "⚙️ Настройки":
        await settings_menu(update, context)
    elif t == "🏆 Достижения":
        await achievements_menu(update, context)
    elif t == "📊 Мультибюджет":
        await multi_budget_menu(update, context)
    elif t == "💰 Долги/Кредиты":
        await debts_menu(update, context)
    elif t == "➕ Добавить долг":
        await add_debt_start(update, context)
    elif t == "🔙 Назад":
        await back(update, context)

async def universal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсал обработчик"""
    t = update.message.text
    buttons_list = [
        "📋 Мои подписки", "➕ Добавить подписку", "💰 Бюджет", "💸 Добавить трату",
        "📈 Добавить доход", "📊 Статистика", "🤖 AI Помощник", "🔔 Напоминания",
        "🏦 Накопления", "🎯 Мои цели", "✏️ Ред. подписку", "⚙️ Настройки",
        "🏆 Достижения", "📊 Мультибюджет", "💰 Долги/Кредиты", "➕ Добавить долг", "🔙 Назад"
    ]
    
    # Дебет қўшиш форматини текшириш
    if t and (t.startswith("я должен") or t.startswith("мне должны")):
        parts = t.split()
        if len(parts) >= 3:
            # Я должен сумма кому описание
            try:
                amount = parse_money(parts[1])
                who = parts[2] if len(parts) > 2 else "неизвестно"
                name = " ".join(parts[3:]) if len(parts) > 3 else "Долг"
                debt_type = 'i_owe' if t.startswith("я должен") else 'owed_to_me'
                
                db.add_debt(
                    update.effective_user.id,
                    name,
                    amount,
                    db.get_user_currency(update.effective_user.id),
                    who,
                    date.today().isoformat(),
                    debt_type
                )
                await update.message.reply_text(f"✅ *Долг добавлен!*\n{name}: {format_money(amount)} {who}", parse_mode="Markdown")
                return
            except:
                pass
    
    if t and t.startswith('/'):
        # Командаларни бошқариш
        if t.startswith('/start'):
            await start(update, context)
        elif t.startswith('/del'):
            await handle_delete(update, context)
        elif t.startswith('/del_debt'):
            await handle_delete(update, context)
        elif t.startswith('/pay_debt'):
            await handle_delete(update, context)
        return
    
    if t and t not in buttons_list:
        if context.user_data.get('ai_mode'):
            await handle_ai(update, context)
        else:
            # Автоматический AI активация
            await update.message.reply_text("🤖 Режим AI активирован! Задайте вопрос.", reply_markup=get_back_keyboard())
            context.user_data['ai_mode'] = True
            await handle_ai(update, context)

# ========== ОТПРАВКА НАПОМИНАНИЙ ==========
send_reminder_to_user = None

async def reminder_sender(user_id: int, text: str):
    """Эслатма юбориш"""
    try:
        if _app:
            await _app.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания {user_id}: {e}")

# ========== ЗАПУСК ==========
_app = None

def main():
    """Ботни ишга тушириш"""
    global _app, send_reminder_to_user
    
    # Windows uchun asyncio sozlamasi
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Эски базани тозалаш (агар колонкалар мавжуд бўлмаса)
    if os.path.exists("finance_bot.db"):
        try:
            import sqlite3
            conn = sqlite3.connect("finance_bot.db")
            c = conn.cursor()
            # Эски базани текшириш
            c.execute("SELECT billing_day FROM subscriptions LIMIT 1")
            c.execute("SELECT language FROM users LIMIT 1")
            conn.close()
        except sqlite3.OperationalError:
            os.remove("finance_bot.db")
            logger.info("🗑 Старая БД удалена, создаю новую...")
    
    # Базани инициализация қилиш
    db.init_db()
    
    # Application яратиш
    app = Application.builder().token(TOKEN).connect_timeout(60).read_timeout(60).build()
    _app = app
    
    # Напоминаниялар учун глобал функцияни ўрнатиш
    send_reminder_to_user = reminder_sender
    reminders.send_reminder_to_user = reminder_sender
    
    # Диалогларни регистрация қилиш
    conv_add_sub = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Добавить подписку"), add_subscription_start)],
        states={
            ADD_SUB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_name)],
            ADD_SUB_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_cost)],
            ADD_SUB_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_currency)],
            ADD_SUB_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_day)],
            ADD_SUB_TRIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_trial)],
            ADD_SUB_TRIAL_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_trial_end)],
            ADD_SUB_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_payment)],
            ADD_SUB_AUTO_RENEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_auto_renew)],
            ADD_SUB_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_budget = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("💰 Бюджет"), set_budget_start)],
        states={
            SET_BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_value)],
            SET_BUDGET_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_currency)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_expense = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("💸 Добавить трату"), add_expense_start)],
        states={
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)],
            ADD_EXPENSE_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_currency)],
            ADD_EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_category)],
            ADD_EXPENSE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_desc)],
            ADD_EXPENSE_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_tags)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_income = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📈 Добавить доход"), add_income_start)],
        states={
            ADD_INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_amount)],
            ADD_INCOME_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_currency)],
            ADD_INCOME_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_source)],
            ADD_INCOME_RECURRING: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_income_recurring)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_saving = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🏦 Накопления"), add_saving_start)],
        states={
            ADD_SAVING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_saving_amount)],
            ADD_SAVING_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_saving_currency)],
            ADD_SAVING_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_saving_purpose)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_goal = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🎯 Мои цели"), add_goal_start)],
        states={
            ADD_GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_name)],
            ADD_GOAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_amount)],
            ADD_GOAL_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_currency)],
            ADD_GOAL_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_deadline)],
            ADD_GOAL_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_priority)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_edit_sub = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✏️ Ред. подписку"), edit_subscription_start)],
        states={
            EDIT_SUBSCRIPTION_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_subscription_get_id)],
            EDIT_SUBSCRIPTION_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_subscription_field)],
            EDIT_SUBSCRIPTION_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_subscription_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_add_debt = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Добавить долг"), add_debt_start)],
        states={
            ADD_DEBT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_type_handler)],
            ADD_DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_name_handler)],
            ADD_DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_amount_handler)],
            ADD_DEBT_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_currency_handler)],
            ADD_DEBT_WHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_who_handler)],
            ADD_DEBT_WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_debt_save_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    conv_multi_budget = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📊 Мультибюджет"), add_multi_budget_start)],
        states={
            ADD_MULTI_BUDGET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_multi_budget_name)],
            ADD_MULTI_BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_multi_budget_amount)],
            ADD_MULTI_BUDGET_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_multi_budget_currency)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("🔙 Назад"), cancel)],
    )
    
    # Хэндлерларни қўшиш
    app.add_handler(conv_add_sub)
    app.add_handler(conv_budget)
    app.add_handler(conv_expense)
    app.add_handler(conv_income)
    app.add_handler(conv_saving)
    app.add_handler(conv_goal)
    app.add_handler(conv_edit_sub)
    app.add_handler(conv_add_debt)
    app.add_handler(conv_multi_budget)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("del", handle_delete))
    app.add_handler(CommandHandler("del_debt", handle_delete))
    app.add_handler(CommandHandler("pay_debt", handle_delete))
    app.add_handler(MessageHandler(filters.Regex("^(📋 Мои подписки|➕ Добавить подписку|💰 Бюджет|💸 Добавить трату|📈 Добавить доход|📊 Статистика|🤖 AI Помощник|🔔 Напоминания|🏦 Накопления|🎯 Мои цели|✏️ Ред. подписку|⚙️ Настройки|🏆 Достижения|📊 Мультибюджет|💰 Долги/Кредиты|➕ Добавить долг|🔙 Назад)$"), button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, universal_handler))
    
    # Напоминанияларни ишга тушириш
    reminders.start_reminder_thread()
    
    # Босилиш маълумоти
    print("\n" + "=" * 70)
    print("💰 ФИНАНСОВЫЙ ПОМОЩНИК ЗАПУЩЕН!")
    print("=" * 70)
    print("✨ ВОЗМОЖНОСТИ:")
    print("   1. 📊 График расм (Pie chart) - 'Статистика'")
    print("   2. 🔔 Smart-напоминания (7,3,1 кун олдин) - 'Напоминания'")
    print("   3. 💰 Долги/Кредитлар тўлиқ ҳисоб - 'Долги/Кредиты'")
    print("   4. 📊 Мультибюджет (алоҳида бюджетлар) - 'Мультибюджет'")
    print("   5. 🏷 Категориялар (қўшиш/ўчириш) - трата қўшганда")
    print("   6. 🏆 Достижения (10,50,100 трат) - 'Достижения'")
    print("   7. 📈 Трендлар (ўсиш/пасайиш) - 'Статистика'")
    print("   8. 💡 Авто-цель таклифи (20%) - доход қўшганда")
    print("   9. 💬 AI контекст (олдинги саволлар) - 'AI Помощник'")
    print("   + 💡 ҚЎШИМЧА ФУНКЦИЯ: Қарзларни тўлиқ ҳисобга олиш системаси!")
    print("=" * 70)
    print("✅ Бот готов к работе!\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()
    