# Per-user история диалога с AI-ассистентом
# In-memory, теряется при редеплое — для коротких сессий это норма

from collections import defaultdict, deque

MAX_HISTORY = 8  # 4 пары user/assistant

_histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def get_history(user_id: int) -> list[dict]:
    """Возвращает список сообщений для передачи в Anthropic API."""
    return list(_histories[user_id])


def append(user_id: int, role: str, text: str) -> None:
    """Добавляет сообщение в историю пользователя."""
    _histories[user_id].append({"role": role, "content": text})


def clear(user_id: int) -> None:
    """Сбрасывает историю пользователя — при выходе из режима ассистента."""
    _histories[user_id].clear()
