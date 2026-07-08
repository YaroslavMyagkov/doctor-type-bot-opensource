# Загрузка markdown-файлов базы знаний для подмешивания в system prompt

import os
from ai.knowledge._index import LESSON_TO_KB

KB_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


def _read_file(filename: str) -> str | None:
    """Читает файл из ai/knowledge/. Возвращает None если файла нет."""
    path = os.path.join(KB_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_for_lesson(lesson_id: str) -> str | None:
    """
    Возвращает содержимое .md файла, привязанного к уроку.
    Если урока нет в маппинге или файл отсутствует — возвращает None.
    """
    filename = LESSON_TO_KB.get(lesson_id)
    if not filename:
        return None
    return _read_file(filename)


def load_all() -> str:
    """
    Конкатенирует все .md файлы из ai/knowledge/ с разделителями.
    Используется для свободных вопросов из главного меню (без контекста урока).
    """
    if not os.path.exists(KB_DIR):
        return ""

    chunks = []
    for filename in sorted(os.listdir(KB_DIR)):
        if not filename.endswith(".md"):
            continue
        content = _read_file(filename)
        if content:
            chunks.append(f"### {filename}\n\n{content}")
    return "\n\n---\n\n".join(chunks)
