# Обёртка над Anthropic API. Вызов Claude Haiku с базой знаний и историей диалога

import os
from anthropic import AsyncAnthropic

from ai.prompts import SYSTEM_PROMPT
from ai.knowledge_loader import load_for_lesson, load_all
from ai import history

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 300

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    """Ленивая инициализация клиента — позволяет тестам подменить API-ключ."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY не задан в переменных окружения")
        _client = AsyncAnthropic(api_key=api_key)
    return _client


def _build_system_text(lesson_id: str | None) -> str:
    """Собирает системный промпт + базу знаний (либо урока, либо всю)."""
    kb_text = None
    if lesson_id:
        kb_text = load_for_lesson(lesson_id)

    if kb_text is None:
        # Урок не задан, или для урока нет файла — грузим всю базу
        kb_text = load_all()

    if kb_text:
        return SYSTEM_PROMPT + "\n\nKNOWLEDGE BASE:\n\n" + kb_text
    return SYSTEM_PROMPT


async def ask_claude(user_id: int, question: str, lesson_id: str | None = None) -> str:
    """
    Главная точка входа. Грузит KB и историю, вызывает Anthropic, обновляет историю.

    lesson_id — если задан, в системный промпт идёт только материал этого урока.
    Если None или нет файла — идёт вся база знаний целиком.
    """
    system_text = _build_system_text(lesson_id)

    # cache_control — кешируем системный блок (5 мин TTL, 10x дешевле при cache hit)
    system = [{
        "type": "text",
        "text": system_text,
        "cache_control": {"type": "ephemeral"}
    }]

    messages = history.get_history(user_id) + [
        {"role": "user", "content": question}
    ]

    client = _get_client()
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
    )
    response_text = msg.content[0].text

    history.append(user_id, "user", question)
    history.append(user_id, "assistant", response_text)

    return response_text
