# Загрузчик контента уроков и практик из .md-файлов.
# Шаги урока: content/steps/{module_id}/{lesson_id}.md — разделены заголовками #
# Практики:   content/steps/{module_id}/{lesson_id}.practice.md — разделены ---
#
# Форматирование: markdown → Telegram MarkdownV1 (одиночные * для bold, _ для italic)

import re
import os
from functools import lru_cache

_DIR = os.path.join(os.path.dirname(__file__), "steps")


# ── Markdown → Telegram ───────────────────────────────────────────────────────

def _convert(text: str) -> str:
    """Конвертирует Markdown-форматирование в Telegram MarkdownV1."""
    # **жирный** → *жирный*  (сначала, чтобы не зацепить одиночные *)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text, flags=re.DOTALL)
    # *курсив* → _курсив_  (одиночные *, не часть **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', text, flags=re.DOTALL)
    # - пункт → — пункт
    text = re.sub(r'^- ', '— ', text, flags=re.MULTILINE)
    return text.strip()


# ── Шаги урока ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=128)
def _parse_steps(module_id: str, lesson_id: str) -> tuple:
    """
    Читает lesson_id.md и возвращает tuple dict-ов шагов:
      {"text": "...", "image": "file_id или None"}

    Каждый заголовок #–###### — начало нового шага.
    Опциональная строка прямо под заголовком вида `image: <file_id>`
    привязывает картинку к этому шагу.
    """
    path = os.path.join(_DIR, module_id, f"{lesson_id}.md")
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    # re.split с группой захвата: [до_первого, заголовок1, тело1, заголовок2, тело2, ...]
    parts = re.split(r'^#{1,6}\s+(.+)$', raw, flags=re.MULTILINE)

    steps = []
    i = 1
    while i < len(parts) - 1:
        heading = parts[i].strip()
        body_raw = parts[i + 1]

        # Ищем image: <file_id> как первую непустую строку тела
        image_file_id = None
        body_lines = body_raw.splitlines()
        remaining_lines = []
        found_image = False
        for line in body_lines:
            if not found_image and re.match(r'^image:\s*\S+', line.strip()):
                image_file_id = re.match(r'^image:\s*(\S+)', line.strip()).group(1)
                found_image = True
            else:
                remaining_lines.append(line)

        body = _convert('\n'.join(remaining_lines).strip())
        steps.append({"text": f"*{heading}*\n\n{body}", "image": image_file_id})
        i += 2
    return tuple(steps)


def get_step_text(module_id: str, lesson_id: str, step_index: int) -> str:
    """Возвращает текст шага в Telegram-формате."""
    return _parse_steps(module_id, lesson_id)[step_index]["text"]


def get_step_image(module_id: str, lesson_id: str, step_index: int) -> str | None:
    """Возвращает file_id картинки для шага или None."""
    return _parse_steps(module_id, lesson_id)[step_index]["image"]


def get_step_count(module_id: str, lesson_id: str) -> int:
    """Возвращает количество шагов в уроке."""
    return len(_parse_steps(module_id, lesson_id))


# ── Практические задания ──────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def get_practice(module_id: str, lesson_id: str) -> list:
    """
    Читает lesson_id.practice.md и возвращает список словарей с заданиями.
    Если файл не существует — возвращает [].
    """
    path = os.path.join(_DIR, module_id, f"{lesson_id}.practice.md")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    blocks = [b.strip() for b in re.split(r'^---\s*$', raw, flags=re.MULTILINE) if b.strip()]
    return [_parse_practice_block(b) for b in blocks]


def get_practice_length(module_id: str, lesson_id: str) -> int:
    """Возвращает количество заданий в практике урока."""
    return len(get_practice(module_id, lesson_id))


def _parse_practice_block(block: str) -> dict:
    """Парсит один блок практического задания."""
    lines = block.strip().splitlines()
    # Первая строка: # тип (choice / case / true_false / open / photo)
    q_type = lines[0].lstrip('#').strip().lower()

    kv: dict = {}
    options: dict = {}
    outcomes: dict = {}
    free_lines: list = []

    for line in lines[1:]:
        if not line.strip():
            free_lines.append('')
            continue
        m_outcome = re.match(r'^outcome_([A-D]):\s*(.*)', line)
        m_option = re.match(r'^([A-D]):\s*(.*)', line)
        m_kv = re.match(r'^(\w+):\s*(.*)', line)
        if m_outcome:
            outcomes[m_outcome.group(1)] = m_outcome.group(2).strip()
        elif m_option:
            options[m_option.group(1)] = m_option.group(2).strip()
        elif m_kv:
            kv[m_kv.group(1).lower()] = m_kv.group(2).strip()
        else:
            free_lines.append(line.strip())

    question_text = '\n'.join(ln for ln in free_lines if ln).strip()

    if q_type == "choice":
        return {
            "type": "CHOICE",
            "question": question_text,
            "options": options,
            "correct": kv.get("correct", ""),
            "feedback_correct": kv.get("ok", ""),
            "feedback_wrong": kv.get("fail", ""),
        }
    if q_type == "case":
        return {
            "type": "CASE",
            "situation": kv.get("situation", ""),
            "question": kv.get("question", "Что ты делаешь?"),
            "options": options,
            "outcomes": outcomes,
            "best": kv.get("best", ""),
            "note": kv.get("note", ""),
        }
    if q_type == "true_false":
        return {
            "type": "TRUE_FALSE",
            "statement": question_text,
            "correct": kv.get("correct", "").lower() == "true",
            "feedback_correct": kv.get("ok", ""),
            "feedback_wrong": kv.get("fail", ""),
        }
    if q_type == "open":
        return {
            "type": "OPEN_REFLECT",
            "question": question_text,
            "sample_answer": kv.get("sample", ""),
        }
    if q_type == "photo":
        return {
            "type": "PHOTO_QUIZ",
            "file_id": kv.get("file_id", ""),
            "question": question_text,
            "options": options,
            "correct": kv.get("correct", ""),
            "feedback_correct": kv.get("ok", ""),
            "feedback_wrong": kv.get("fail", ""),
        }
    raise ValueError(f"Unknown practice type: {q_type!r} in block:\n{block[:100]}")
