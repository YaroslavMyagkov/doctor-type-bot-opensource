# Обработчики режима AI-ассистента
# Точки входа: из главного меню (свободный вопрос) и из шага урока (контекстный вопрос)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ai.client import ask_claude
from ai import history, rate_limit
from handlers._helpers import safe_edit
from handlers._images import AI_IMAGE_ID, MENU_IMAGE_ID


def build_ai_exit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура внутри режима ассистента — выход и быстрый возврат в меню."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Закончить разговор", callback_data="ai_exit")],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])


async def enter_ai_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Включает режим ассистента.
    callback_data форматы:
      - ai_enter                              → свободный вопрос, без контекста урока
      - ai_enter_module_01_lesson_01          → вопрос в контексте конкретного урока
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    lesson_id: str | None = None
    if len(parts) >= 6:
        # ai_enter_module_XX_lesson_YY → берём lesson_YY
        lesson_id = f"{parts[4]}_{parts[5]}"

    # Сбрасываем историю предыдущей сессии при входе
    user_id = query.from_user.id
    history.clear(user_id)

    context.user_data["ai_mode"] = True
    context.user_data["ai_lesson_context"] = lesson_id

    if lesson_id:
        prompt_text = (
            "Я — ИИ-ассистент доктор Тайп, коротко отвечу на любой вопрос по этому уроку.\n\n"
            "Спрашивай, если что-то непонятно или хочешь повторить."
        )
    else:
        prompt_text = (
            "Я — ИИ-ассистент доктор Тайп, коротко отвечу на любой вопрос по теме нашего курса.\n\n"
            "Спрашивай, если что-то непонятно или хочешь повторить."
        )

    try:
        await query.message.delete()
    except Exception:
        pass
    sent = await query.message.chat.send_photo(
        photo=AI_IMAGE_ID,
        caption=prompt_text,
        reply_markup=build_ai_exit_keyboard()
    )
    context.user_data["last_ai_msg_id"] = sent.message_id


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает текстовое сообщение студента в режиме ассистента.
    Вызывается из text-диспетчера в main.py только когда ai_mode == True.
    """
    user_id = update.effective_user.id
    question = update.message.text
    lesson_id = context.user_data.get("ai_lesson_context")

    # Убираем кнопки с предыдущего сообщения бота — они уже неактуальны
    last_msg_id = context.user_data.get("last_ai_msg_id")
    if last_msg_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=last_msg_id,
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception:
            pass

    # Проверяем дневной лимит
    if not rate_limit.can_request(user_id):
        sent = await update.message.reply_text(
            f"На сегодня лимит вопросов исчерпан ({rate_limit.DAILY_LIMIT} в день). "
            "Возвращайся завтра.",
            reply_markup=build_ai_exit_keyboard()
        )
        context.user_data["last_ai_msg_id"] = sent.message_id
        return

    # Показываем typing — пока Claude отвечает
    await update.message.chat.send_action(action="typing")

    try:
        answer = await ask_claude(user_id, question, lesson_id)
        rate_limit.increment(user_id)  # засчитываем только после успешного ответа
    except Exception as e:
        import traceback
        print(f"[ai] ERROR: {traceback.format_exc()}")
        sent = await update.message.reply_text(
            "Не получилось получить ответ. Попробуй ещё раз через минуту "
            "или вернись в меню.",
            reply_markup=build_ai_exit_keyboard()
        )
        context.user_data["last_ai_msg_id"] = sent.message_id
        return

    # Telegram не любит Markdown с неэкранированными спецсимволами — шлём как обычный текст
    sent = await update.message.reply_text(
        text=answer,
        reply_markup=build_ai_exit_keyboard()
    )
    context.user_data["last_ai_msg_id"] = sent.message_id


async def exit_ai_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выход из режима ассистента — сбрасывает флаги и историю.
    Если вход был из контекста урока ("Спросить по этому уроку") — возвращает
    студента на тот же шаг урока. Иначе показывает главное меню.
    callback_data: ai_exit
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lesson_context = context.user_data.get("ai_lesson_context")
    history.clear(user_id)

    context.user_data["ai_mode"] = False
    context.user_data["ai_lesson_context"] = None
    context.user_data["last_ai_msg_id"] = None

    # Убираем кнопки с последнего AI-сообщения — оно остаётся в истории
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
    except Exception:
        pass

    # Если был контекст урока — возвращаем студента на тот же шаг
    if lesson_context:
        try:
            from storage.sheets import get_or_create_student
            from content.modules import get_lesson
            from content.md_loader import get_step_text, get_practice_length
            from handlers.course import build_step_navigation

            username = query.from_user.username or "unknown"
            student = get_or_create_student(user_id, username)
            module_id = student.get("current_module", "module_01")
            lesson_id = student.get("current_lesson", lesson_context)
            step = int(student.get("current_step", 0))

            lesson = get_lesson(module_id, lesson_id)
            if lesson:
                total_steps = len(lesson["steps"])
                step = min(max(step, 0), total_steps - 1)
                has_practice = get_practice_length(module_id, lesson_id) > 0
                caption = f"*{lesson['title']}* · шаг {step + 1} из {total_steps}\n\n"
                await query.message.chat.send_message(
                    text=caption + get_step_text(module_id, lesson_id, step),
                    reply_markup=build_step_navigation(
                        step, total_steps, module_id, lesson_id, has_practice
                    ),
                    parse_mode="Markdown"
                )
                return
        except Exception:
            import traceback
            print(f"[ai exit → lesson] ERROR: {traceback.format_exc()}")
            # упадём на главное меню ниже

    # Иначе — главное меню новым сообщением
    from handlers.menu import build_main_menu
    await query.message.chat.send_photo(
        photo=MENU_IMAGE_ID,
        caption="Меню:",
        reply_markup=build_main_menu()
    )


def reset_ai_state(context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None):
    """
    Утилита для вызова из других обработчиков (например /menu, /start, go_menu).
    Сбрасывает AI-режим, OPEN_REFLECT-сессию и очищает историю —
    после неё user_data чистый, текстовый диспетчер не путается.
    """
    context.user_data["ai_mode"] = False
    context.user_data["ai_lesson_context"] = None
    context.user_data["last_ai_msg_id"] = None
    context.user_data.pop("open_reflect", None)
    context.user_data.pop("open_reflect_hint_id", None)
    context.user_data.pop("open_reflect_wrong_ids", None)
    context.user_data.pop("feedback_mode", None)
    context.user_data.pop("feedback_hint_id", None)
    context.user_data.pop("feedback_wrong_ids", None)
    if user_id is not None:
        history.clear(user_id)
