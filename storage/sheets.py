# Модуль для работы с Google Sheets — хранение прогресса студентов

import gspread
import os
from datetime import date, datetime

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
SPREADSHEET_NAME = "doctor_type_db"

# Заголовки таблицы — порядок важен, должен совпадать с new_student ниже
HEADERS = [
    "user_id", "username",
    "current_module", "current_lesson", "current_step",
    "current_practice_step",                              # индекс текущего вопроса практики
    "completed_lessons", "completed_practice", "completed_modules",
    "last_seen"
]


def get_sheet():
    """Подключается к Google Sheets — локально через файл, на сервере через переменную окружения"""
    import json

    google_creds_env = os.environ.get("GOOGLE_CREDENTIALS")

    if google_creds_env:
        creds_dict = json.loads(google_creds_env)
        client = gspread.service_account_from_dict(creds_dict)
    else:
        client = gspread.service_account(filename=CREDENTIALS_FILE)

    return client.open_by_key("1IvURKn8jsF2c8h3p2OhClcrUfYyWdYPeyj8WAJFkqPQ").sheet1


def get_or_create_student(user_id: int, username: str) -> dict:
    """
    Ищет студента по user_id.
    Если не находит — создаёт новую строку с начальными значениями.
    """
    sheet = get_sheet()
    all_values = sheet.get_all_values()

    if len(all_values) == 0:
        sheet.append_row(HEADERS)
        return _create_student(sheet, user_id, username)

    for row in all_values[1:]:
        if len(row) > 0 and row[0] == str(user_id):
            return _row_to_dict(row)

    return _create_student(sheet, user_id, username)


def _create_student(sheet, user_id: int, username: str) -> dict:
    """Создаёт новую строку студента в таблице"""
    new_student = {
        "user_id": str(user_id),
        "username": username,
        "current_module": "module_01",
        "current_lesson": "lesson_01",
        "current_step": "0",
        "current_practice_step": "",
        "completed_lessons": "",
        "completed_practice": "",
        "completed_modules": "",
        "last_seen": str(date.today())
    }
    sheet.append_row([new_student[h] for h in HEADERS])
    return new_student


def _row_to_dict(row: list) -> dict:
    """Превращает строку таблицы в словарь по заголовкам"""
    padded = row + [""] * (len(HEADERS) - len(row))
    return dict(zip(HEADERS, padded))


def update_student(user_id: int, **kwargs) -> None:
    """
    Обновляет поля студента в таблице.
    Пример: update_student(123, current_step="3", last_seen="2026-03-30")
    """
    sheet = get_sheet()
    all_values = sheet.get_all_values()

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > 0 and row[0] == str(user_id):
            for key, value in kwargs.items():
                if key in HEADERS:
                    col = HEADERS.index(key) + 1
                    sheet.update_cell(i, col, str(value))
            return


def complete_lesson(user_id: int, lesson_id: str) -> None:
    """Добавляет урок в список пройденных уроков студента"""
    sheet = get_sheet()
    all_values = sheet.get_all_values()

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > 0 and row[0] == str(user_id):
            student = _row_to_dict(row)
            completed = student.get("completed_lessons", "")
            lessons_list = [l for l in completed.split(",") if l]

            if lesson_id not in lessons_list:
                lessons_list.append(lesson_id)
                col = HEADERS.index("completed_lessons") + 1
                sheet.update_cell(i, col, ",".join(lessons_list))
            return


def complete_practice(user_id: int, lesson_id: str, module_id: str, all_module_lessons: list) -> None:
    """
    Помечает практику урока как пройденную и сбрасывает current_practice_step.
    Если все уроки модуля пройдены — помечает модуль как завершённый.
    """
    sheet = get_sheet()
    all_values = sheet.get_all_values()

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > 0 and row[0] == str(user_id):
            student = _row_to_dict(row)

            # Обновляем completed_practice
            practice_list = [l for l in student.get("completed_practice", "").split(",") if l]
            if lesson_id not in practice_list:
                practice_list.append(lesson_id)
            col_practice = HEADERS.index("completed_practice") + 1
            sheet.update_cell(i, col_practice, ",".join(practice_list))

            # Сбрасываем current_practice_step — урок завершён
            col_ps = HEADERS.index("current_practice_step") + 1
            sheet.update_cell(i, col_ps, "")

            # Проверяем, все ли уроки модуля пройдены
            all_done = all(l in practice_list for l in all_module_lessons)
            if all_done:
                modules_list = [m for m in student.get("completed_modules", "").split(",") if m]
                if module_id not in modules_list:
                    modules_list.append(module_id)
                    col_modules = HEADERS.index("completed_modules") + 1
                    sheet.update_cell(i, col_modules, ",".join(modules_list))
            return


def get_answers_sheet():
    """
    Возвращает лист open_answers для хранения ответов на открытые вопросы.
    Если лист не существует — создаёт его с заголовками.
    """
    import json
    google_creds_env = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds_env:
        creds_dict = json.loads(google_creds_env)
        client = gspread.service_account_from_dict(creds_dict)
    else:
        client = gspread.service_account(filename=CREDENTIALS_FILE)

    spreadsheet = client.open_by_key("1IvURKn8jsF2c8h3p2OhClcrUfYyWdYPeyj8WAJFkqPQ")

    try:
        return spreadsheet.worksheet("open_answers")
    except gspread.exceptions.WorksheetNotFound:
        # Создаём лист если его нет, добавляем заголовки
        sheet = spreadsheet.add_worksheet(title="open_answers", rows=1000, cols=7)
        sheet.append_row(["timestamp", "user_id", "username", "module_id", "lesson_id", "question_index", "answer"])
        return sheet


def get_feedback_sheet():
    """
    Возвращает лист feedback для хранения отзывов студентов.
    Если лист не существует — создаёт его с заголовками.
    """
    import json
    google_creds_env = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds_env:
        creds_dict = json.loads(google_creds_env)
        client = gspread.service_account_from_dict(creds_dict)
    else:
        client = gspread.service_account(filename=CREDENTIALS_FILE)

    spreadsheet = client.open_by_key("1IvURKn8jsF2c8h3p2OhClcrUfYyWdYPeyj8WAJFkqPQ")

    try:
        return spreadsheet.worksheet("feedback")
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="feedback", rows=1000, cols=4)
        sheet.append_row(["timestamp", "user_id", "username", "feedback"])
        return sheet


def save_feedback(user_id: int, username: str, feedback_text: str) -> None:
    """Сохраняет отзыв студента в лист feedback."""
    sheet = get_feedback_sheet()
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(user_id),
        username,
        feedback_text
    ])


def save_open_answer(user_id: int, username: str, module_id: str, lesson_id: str, q_index: int, answer: str) -> None:
    """Сохраняет ответ студента на открытый вопрос в лист open_answers."""
    sheet = get_answers_sheet()
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(user_id),
        username,
        module_id,
        lesson_id,
        str(q_index),
        answer
    ])


def is_lesson_accessible(student: dict, module_id: str, lesson_id: str, modules: list) -> bool:
    """
    Проверяет, доступен ли урок студенту.
    Первый урок первого модуля — всегда доступен.
    Остальные — если предыдущий урок есть в completed_practice.
    """
    completed_practice = [l for l in student.get("completed_practice", "").split(",") if l]
    completed_modules = [m for m in student.get("completed_modules", "").split(",") if m]

    for m_idx, module in enumerate(modules):
        if module["id"] != module_id:
            continue

        if m_idx > 0:
            prev_module_id = modules[m_idx - 1]["id"]
            if prev_module_id not in completed_modules:
                return False

        for l_idx, lesson in enumerate(module["lessons"]):
            if lesson["id"] != lesson_id:
                continue
            if l_idx == 0:
                return True
            prev_lesson_id = module["lessons"][l_idx - 1]["id"]
            return prev_lesson_id in completed_practice

    return False