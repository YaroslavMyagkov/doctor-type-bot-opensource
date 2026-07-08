# Движок практических заданий — обрабатывает все типы вопросов
# Типы: CHOICE, CASE, TRUE_FALSE, OPEN_REFLECT, PHOTO_QUIZ

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from content.modules import get_lesson
from content.md_loader import get_practice as _load_practice, get_practice_length as _load_practice_length
from storage.sheets import complete_practice, update_student, save_open_answer
from datetime import date
from handlers._helpers import safe_edit, cleanup_lesson_photos


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def get_practice_question(module_id: str, lesson_id: str, q_index: int) -> dict | None:
    """Возвращает вопрос практики по индексу. None если вопросов нет или индекс вышел за границы."""
    practice = _load_practice(module_id, lesson_id)
    if q_index >= len(practice):
        return None
    return practice[q_index]


def get_practice_length(module_id: str, lesson_id: str) -> int:
    """Возвращает количество вопросов в практике урока."""
    return _load_practice_length(module_id, lesson_id)


def make_finish_keyboard(module_id: str, lesson_id: str) -> InlineKeyboardMarkup:
    """Кнопка завершения урока — показывается после последнего вопроса."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Завершить урок →", callback_data=f"finish_{module_id}_{lesson_id}")],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])


def make_next_question_keyboard(module_id: str, lesson_id: str, next_index: int) -> InlineKeyboardMarkup:
    """Кнопка перехода к следующему вопросу практики."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Следующий вопрос →", callback_data=f"practice_{module_id}_{lesson_id}_{next_index}")],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])


def question_counter(q_index: int, total: int) -> str:
    """Строка-заголовок вида 'Вопрос 2 из 4'."""
    return f"_Вопрос {q_index + 1} из {total}_\n\n"


def save_practice_progress(user_id: int, module_id: str, lesson_id: str, q_index: int):
    """Сохраняет текущий индекс вопроса практики в Sheets."""
    update_student(
        user_id,
        current_practice_step=str(q_index),
        current_module=module_id,
        current_lesson=lesson_id,
        last_seen=str(date.today())
    )


# ─── Точка входа: показать вопрос практики ────────────────────────────────────

async def handle_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Точка входа в практику. Вызывается при нажатии 'К практике →' в конце урока
    или при переходе между вопросами.

    callback_data форматы:
      - practice_module_01_lesson_01        → первый вопрос (индекс 0)
      - practice_module_01_lesson_01_2      → вопрос с индексом 2
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    # parts: ["practice", "module", "01", "lesson", "01"] или [..., "2"]
    module_id = f"{parts[1]}_{parts[2]}"
    lesson_id = f"{parts[3]}_{parts[4]}"
    q_index = int(parts[5]) if len(parts) > 5 else 0

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)

    # Сохраняем прогресс — студент дошёл до этого вопроса
    user_id = query.from_user.id
    save_practice_progress(user_id, module_id, lesson_id, q_index)

    # Удаляем старое фото, показываем practice_image для всех вопросов кроме PHOTO_QUIZ
    await cleanup_lesson_photos(context, context.bot, query.message.chat_id)
    if question and question.get("type") != "PHOTO_QUIZ":
        lesson_data = get_lesson(module_id, lesson_id)
        practice_image = lesson_data.get("practice_image") if lesson_data else None
        if practice_image:
            # Фото выше текста: удаляем nav, шлём фото — вопрос появится ниже через safe_edit fallback
            try:
                await query.message.delete()
            except Exception:
                pass
            photo_msg = await query.message.chat.send_photo(photo=practice_image)
            context.user_data["step_photo_msg_id"] = photo_msg.message_id

    if not question:
        # Практики нет или закончилась — сразу показываем кнопку завершить урок
        await safe_edit(
            query,
            text="Практика завершена.",
            reply_markup=make_finish_keyboard(module_id, lesson_id)
        )
        return

    q_type = question.get("type")

    if q_type == "CHOICE":
        await show_choice(query, question, module_id, lesson_id, q_index, total)
    elif q_type == "CASE":
        await show_case(query, question, module_id, lesson_id, q_index, total)
    elif q_type == "TRUE_FALSE":
        await show_true_false(query, question, module_id, lesson_id, q_index, total)
    elif q_type == "OPEN_REFLECT":
        await show_open_reflect(query, question, module_id, lesson_id, q_index, total, context)
    elif q_type == "PHOTO_QUIZ":
        await show_photo_quiz(query, question, module_id, lesson_id, q_index, total)
    else:
        await safe_edit(query, f"Неизвестный тип вопроса: {q_type}")


# ─── CHOICE ───────────────────────────────────────────────────────────────────

async def show_choice(query, question: dict, module_id: str, lesson_id: str, q_index: int, total: int):
    """Показывает вопрос с выбором одного правильного варианта."""
    text = question_counter(q_index, total)
    text += f"*{question['question']}*\n\n"
    for key, val in question["options"].items():
        text += f"{key}) {val}\n"

    # callback_data: choice_answer_module_01_lesson_01_0_B
    keyboard = [
        [InlineKeyboardButton(key, callback_data=f"choice_answer_{module_id}_{lesson_id}_{q_index}_{key}")]
        for key in question["options"]
    ]
    keyboard.append([InlineKeyboardButton("В меню", callback_data="go_menu")])

    await safe_edit(
        query,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_choice_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ответ на CHOICE.
    callback_data: choice_answer_module_01_lesson_01_0_B
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])
    chosen = parts[7]

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    is_correct = chosen == question["correct"]

    if is_correct:
        feedback = f"*Верно.*\n\n{question['feedback_correct']}"
    else:
        feedback = f"*Не совсем.*\n\n{question['feedback_wrong']}"

    next_index = q_index + 1
    is_last = next_index >= total

    if is_last:
        keyboard = make_finish_keyboard(module_id, lesson_id)
    else:
        keyboard = make_next_question_keyboard(module_id, lesson_id, next_index)

    await safe_edit(
        query,
        text=feedback,
        reply_markup=keyboard
    )


# ─── CASE ─────────────────────────────────────────────────────────────────────

async def show_case(query, question: dict, module_id: str, lesson_id: str, q_index: int, total: int):
    """Показывает кейс-задание с вариантами и последствиями."""
    text = question_counter(q_index, total)
    text += f"*Кейс*\n\n{question['situation']}\n\n"
    text += f"*{question['question']}*\n\n"
    for key, val in question["options"].items():
        text += f"{key}) {val}\n"

    # callback_data: case_answer_module_01_lesson_01_0_A
    keyboard = [
        [InlineKeyboardButton(key, callback_data=f"case_answer_{module_id}_{lesson_id}_{q_index}_{key}")]
        for key in question["options"]
    ]
    keyboard.append([InlineKeyboardButton("В меню", callback_data="go_menu")])

    await safe_edit(
        query,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_case_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор варианта в кейсе.
    callback_data: case_answer_module_01_lesson_01_0_A
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])
    chosen = parts[7]

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    best = question.get("best")
    outcome = question["outcomes"][chosen]
    is_best = chosen == best

    next_index = q_index + 1
    is_last = next_index >= total
    note = question.get("note", "")

    if is_best:
        text = f"*Вариант {chosen} — оптимальный.*\n\n{outcome}"
        if note:
            text += f"\n\n_{note}_"
        keyboard = make_finish_keyboard(module_id, lesson_id) if is_last else make_next_question_keyboard(module_id, lesson_id, next_index)
    else:
        text = f"*Вариант {chosen}*\n\n{outcome}"
        if note:
            text += f"\n\n_{note}_"
        retry_callback = f"case_retry_{module_id}_{lesson_id}_{q_index}"

        if is_last:
            text += f"\n\nОптимальный вариант — {best}."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Попробовать ещё", callback_data=retry_callback)],
                [InlineKeyboardButton("Завершить урок →", callback_data=f"finish_{module_id}_{lesson_id}")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")]
            ])
        else:
            text += f"\n\nОптимальный вариант — {best}. Можешь попробовать ещё или двигаться дальше."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Попробовать ещё", callback_data=retry_callback)],
                [InlineKeyboardButton("Двигаться дальше →", callback_data=f"case_proceed_{module_id}_{lesson_id}_{q_index}")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")]
            ])

    await safe_edit(
        query,
        text=text,
        reply_markup=keyboard
    )


async def handle_case_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает к кейсу для повторной попытки."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    await show_case(query, question, module_id, lesson_id, q_index, total)


async def handle_case_proceed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Двигаться дальше из кейса без выбора оптимального варианта.
    Практика засчитывается, бот показывает оптимальный ответ.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    best = question.get("best")
    best_outcome = question["outcomes"][best]

    next_index = q_index + 1
    is_last = next_index >= total

    text = f"_Оптимальный вариант — {best}:_\n\n{best_outcome}"

    if is_last:
        keyboard = make_finish_keyboard(module_id, lesson_id)
    else:
        keyboard = make_next_question_keyboard(module_id, lesson_id, next_index)

    await safe_edit(
        query,
        text=text,
        reply_markup=keyboard
    )


# ─── TRUE_FALSE ───────────────────────────────────────────────────────────────

async def show_true_false(query, question: dict, module_id: str, lesson_id: str, q_index: int, total: int):
    """Показывает утверждение с кнопками Верно/Неверно."""
    text = question_counter(q_index, total)
    text += f"*Верно или нет?*\n\n{question['statement']}"

    # callback_data: tf_answer_module_01_lesson_01_0_true
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Верно", callback_data=f"tf_answer_{module_id}_{lesson_id}_{q_index}_true"),
            InlineKeyboardButton("Неверно", callback_data=f"tf_answer_{module_id}_{lesson_id}_{q_index}_false")
        ],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])
    await safe_edit(
        query,
        text=text,
        reply_markup=keyboard
    )


async def handle_tf_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ответ на TRUE_FALSE.
    callback_data: tf_answer_module_01_lesson_01_0_true
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])
    chosen = parts[7] == "true"

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    is_correct = chosen == question["correct"]

    if is_correct:
        feedback = f"*Верно.*\n\n{question['feedback_correct']}"
    else:
        feedback = f"*Не так.*\n\n{question['feedback_wrong']}"

    next_index = q_index + 1
    is_last = next_index >= total

    if is_last:
        keyboard = make_finish_keyboard(module_id, lesson_id)
    else:
        keyboard = make_next_question_keyboard(module_id, lesson_id, next_index)

    await safe_edit(
        query,
        text=feedback,
        reply_markup=keyboard
    )


# ─── OPEN_REFLECT ─────────────────────────────────────────────────────────────

async def show_open_reflect(query, question: dict, module_id: str, lesson_id: str, q_index: int, total: int, context):
    """
    Показывает открытый вопрос. Студент отвечает реплаем на это сообщение.
    """
    text = question_counter(q_index, total)
    text += (
        f"*{question['question']}*\n\n"
        f"_Ответь реплаем на это сообщение: нажми на него и выбери «Ответить»._"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])

    # Сохраняем реальный message_id — safe_edit может прислать новое сообщение
    # (например, если nav-сообщение было удалено перед показом practice_image)
    sent_msg_id = await safe_edit(
        query,
        text=text,
        reply_markup=keyboard
    )

    context.user_data["open_reflect"] = {
        "module_id": module_id,
        "lesson_id": lesson_id,
        "q_index": q_index,
        "message_id": sent_msg_id
    }


async def handle_open_reflect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает текстовый ответ студента на OPEN_REFLECT.
    Если студент пишет произвольный текст вне этого режима — молча игнорируем
    (не спамим подсказками).
    Если активен режим AI-ассистента — этот обработчик не должен сюда попадать
    (диспетчер в main.py роутит сообщение в handle_ai_message). Ранний return —
    дополнительная защита.
    """
    if context.user_data.get("ai_mode"):
        return

    reflect_data = context.user_data.get("open_reflect")

    # Нет активного открытого вопроса — удаляем случайное сообщение из чата
    if not reflect_data:
        try:
            await update.message.delete()
        except Exception:
            pass
        return

    # Сообщение должно быть реплаем именно на сообщение с вопросом
    if not update.message.reply_to_message or \
       update.message.reply_to_message.message_id != reflect_data["message_id"]:
        # Удаляем предыдущую подсказку, если она уже висит — не накапливаем
        prev_hint = context.user_data.pop("open_reflect_hint_id", None)
        if prev_hint:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=prev_hint
                )
            except Exception:
                pass
        sent = await update.message.reply_text(
            "Чтобы ответ засчитался, нужно ответить именно реплаем "
            "на сообщение с вопросом — нажми на него и выбери «Ответить».",
            parse_mode="Markdown"
        )
        context.user_data["open_reflect_hint_id"] = sent.message_id
        # Запоминаем ID самого ошибочного сообщения — удалим когда придёт верный ответ
        context.user_data["open_reflect_wrong_ids"] = \
            context.user_data.get("open_reflect_wrong_ids", []) + [update.message.message_id]
        return

    module_id = reflect_data["module_id"]
    lesson_id = reflect_data["lesson_id"]
    q_index = reflect_data["q_index"]
    user_answer = update.message.text

    # Удаляем подсказку и все ошибочные сообщения пользователя
    hint_id = context.user_data.pop("open_reflect_hint_id", None)
    wrong_ids = context.user_data.pop("open_reflect_wrong_ids", [])
    for msg_id in ([hint_id] if hint_id else []) + wrong_ids:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=msg_id
            )
        except Exception:
            pass

    # Сохраняем ответ временно — отправим в Sheets после явного подтверждения
    reflect_data["pending_answer"] = user_answer

    confirm_text = (
        f"Твой ответ:\n\n_{user_answer}_\n\n"
        "Отправить его? Преподаватель сможет его увидеть."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Отправить", callback_data=f"reflect_submit_{module_id}_{lesson_id}_{q_index}")],
        [InlineKeyboardButton("Переписать ответ", callback_data=f"reflect_retry_{module_id}_{lesson_id}_{q_index}")]
    ])
    sent = await update.message.reply_text(
        text=confirm_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    reflect_data["confirm_msg_id"] = sent.message_id


async def handle_reflect_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Подтверждение отправки ответа на OPEN_REFLECT.
    Сохраняет ответ в Sheets, показывает образцовый ответ без кнопки «Переписать».
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])

    reflect_data = context.user_data.get("open_reflect", {})
    user_answer = reflect_data.get("pending_answer", "")
    question_message_id = reflect_data.get("message_id")

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)

    # Сохраняем ответ в Sheets
    user_id = query.from_user.id
    username = query.from_user.username or "unknown"
    save_open_answer(user_id, username, module_id, lesson_id, q_index, user_answer)

    sample = question.get("sample_answer", "")
    next_index = q_index + 1
    is_last = next_index >= total

    text = f"Ответ сохранён.\n\n*Один из возможных ответов:*\n{sample}"

    if is_last:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Завершить урок →", callback_data=f"finish_{module_id}_{lesson_id}")],
            [InlineKeyboardButton("В меню", callback_data="go_menu")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Следующий вопрос →", callback_data=f"practice_{module_id}_{lesson_id}_{next_index}")],
            [InlineKeyboardButton("В меню", callback_data="go_menu")]
        ])

    context.user_data.pop("open_reflect", None)

    # Удаляем оригинальное сообщение-вопрос
    if question_message_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=question_message_id
            )
        except Exception:
            pass

    # Редактируем подтверждение → показываем образцовый ответ
    await safe_edit(query, text=text, reply_markup=keyboard)


async def handle_reflect_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает к OPEN_REFLECT вопросу для повторного ответа."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])

    # Удаляем старое сообщение-вопрос, чтобы не оставался дубль после safe_edit
    reflect_data = context.user_data.get("open_reflect", {})
    old_question_id = reflect_data.get("message_id")
    if old_question_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=old_question_id
            )
        except Exception:
            pass

    # Сбрасываем временный ответ
    reflect_data.pop("pending_answer", None)
    reflect_data.pop("confirm_msg_id", None)

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    await show_open_reflect(query, question, module_id, lesson_id, q_index, total, context)


# ─── PHOTO_QUIZ ───────────────────────────────────────────────────────────────

async def show_photo_quiz(query, question: dict, module_id: str, lesson_id: str, q_index: int, total: int):
    """
    Показывает вопрос с картинкой. По механике аналогичен CHOICE.
    Удаляет предыдущее сообщение и отправляет фото с подписью.
    """
    caption = question_counter(q_index, total)
    caption += f"*{question['question']}*\n\n"
    for key, val in question["options"].items():
        caption += f"{key}) {val}\n"

    # callback_data: pq_answer_module_01_lesson_01_0_C
    keyboard = [
        [InlineKeyboardButton(key, callback_data=f"pq_answer_{module_id}_{lesson_id}_{q_index}_{key}")]
        for key in question["options"]
    ]
    keyboard.append([InlineKeyboardButton("В меню", callback_data="go_menu")])

    # Поддерживаем оба варианта: file_id (приоритет) или image_url
    photo_source = question.get("file_id") or question.get("image_url")

    await query.message.delete()
    await query.message.chat.send_photo(
        photo=photo_source,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_pq_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ответ на PHOTO_QUIZ — аналогично CHOICE.
    callback_data: pq_answer_module_01_lesson_01_0_C
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    module_id = f"{parts[2]}_{parts[3]}"
    lesson_id = f"{parts[4]}_{parts[5]}"
    q_index = int(parts[6])
    chosen = parts[7]

    question = get_practice_question(module_id, lesson_id, q_index)
    total = get_practice_length(module_id, lesson_id)
    is_correct = chosen == question["correct"]

    if is_correct:
        feedback = f"*Верно.*\n\n{question['feedback_correct']}"
    else:
        feedback = f"*Не совсем.*\n\n{question['feedback_wrong']}"

    next_index = q_index + 1
    is_last = next_index >= total

    if is_last:
        keyboard = make_finish_keyboard(module_id, lesson_id)
    else:
        keyboard = make_next_question_keyboard(module_id, lesson_id, next_index)

    await query.edit_message_caption(
        caption=feedback,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
