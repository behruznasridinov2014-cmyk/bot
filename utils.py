from datetime import datetime, date

def format_date(dt):
    if isinstance(dt, str):
        dt = date.fromisoformat(dt)
    return dt.strftime("%d.%m.%Y")

def parse_billing_day(day_str: str) -> int:
    """Преобразует строку в день месяца (1-31)"""
    try:
        day = int(day_str)
        if 1 <= day <= 31:
            return day
    except:
        pass
    return 1  # значение по умолчанию

def format_currency(amount: float, currency: str = "$") -> str:
    return f"{amount:.2f} {currency}"