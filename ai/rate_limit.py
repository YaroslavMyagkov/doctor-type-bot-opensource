# Лимит запросов к AI-ассистенту: не более DAILY_LIMIT в день на пользователя.
# In-memory — сбрасывается при редеплое Railway. Для образовательного бота это норма:
# в худшем случае студент получит несколько лишних запросов после рестарта сервиса.

from datetime import date

DAILY_LIMIT = 5

# dict[user_id -> {"date": "2026-05-21", "count": 3}]
_usage: dict[int, dict] = {}


def _ensure_today(user_id: int) -> None:
    today = str(date.today())
    if user_id not in _usage or _usage[user_id]["date"] != today:
        _usage[user_id] = {"date": today, "count": 0}


def can_request(user_id: int) -> bool:
    """True если у пользователя остались запросы на сегодня."""
    _ensure_today(user_id)
    return _usage[user_id]["count"] < DAILY_LIMIT


def increment(user_id: int) -> None:
    """Засчитывает один запрос. Вызывать после успешного ответа ассистента."""
    _ensure_today(user_id)
    _usage[user_id]["count"] += 1


def remaining(user_id: int) -> int:
    """Сколько запросов осталось на сегодня."""
    _ensure_today(user_id)
    return max(0, DAILY_LIMIT - _usage[user_id]["count"])
