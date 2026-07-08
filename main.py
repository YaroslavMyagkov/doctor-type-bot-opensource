# Точка входа — здесь запускается бот

import logging
from dotenv import load_dotenv
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from storage.sheets import get_or_create_student, update_student
from content.modules import get_lesson
from handlers.menu import menu, handle_menu_callback, build_main_menu, handle_reset_confirm, handle_reset_do, handle_feedback_text
from handlers.course import show_module_intro, handle_step, handle_finish_lesson
from handlers.practice import (
    handle_practice,
    handle_choice_answer,
    handle_case_answer,
    handle_case_retry,
    handle_case_proceed,
    handle_tf_answer,
    handle_open_reflect_text,
    handle_reflect_submit,
    handle_reflect_retry,
    handle_pq_answer,
)
from handlers.ai import (
    enter_ai_mode,
    handle_ai_message,
    exit_ai_mode,
    reset_ai_state,
)

load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие, создание профиля, экран возврата при наличии прогресса"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # /start всегда сбрасывает режим ассистента
    reset_ai_state(context, user_id=user_id)

    try:
        student = get_or_create_student(user_id, username)

        has_progress = (
            int(student.get("current_step", 0)) > 0
            or student.get("completed_lessons", "")
            or student.get("completed_practice", "")
        )

        update_student(user_id, last_seen=str(date.today()))

        if has_progress:
            # Возвращающийся студент — показываем экран продолжения
            module_id = student.get("current_module", "module_01")
            lesson_id = student.get("current_lesson", "lesson_01")
            step = int(student.get("current_step", 0))

            lesson = get_lesson(module_id, lesson_id)
            lesson_title = lesson["title"] if lesson else lesson_id

            keyboard = [
                [InlineKeyboardButton("Продолжить", callback_data=f"step_{module_id}_{lesson_id}_{step}")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")],
            ]
            await update.message.reply_text(
                f"С возвращением.\n\n"
                f"Ты остановился на уроке: *{lesson_title}*, шаг {step + 1}.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            # Новый студент — онбординг с фото
            from handlers._images import ONBOARDING_IMAGE_ID
            onboarding_text = (
                "Привет, Я Доктор Тайп — проводник в мир веба. "
                "В этом боте ты сможешь пройти курс по основам веб-технологий, "
                "сделанный специально для графических дизайнеров. "
                "В нём нет ничего лишнего: как устроен интернет, как работает браузер, "
                "базовый HTML и CSS, основы UX/UI. "
                "Четыре модуля, каждый проходится примерно за полчаса.\n\n"
                "Курс рассчитан на параллельное прохождение с учёбой — не заменяет занятия, "
                "а помогает разобраться в теме заранее или повторить после. "
                "Если в процессе обучения появился вопрос — можно спросить прямо здесь "
                "у DoctorType.Ai, встроенного ассистента."
            )
            await update.message.chat.send_photo(
                photo=ONBOARDING_IMAGE_ID,
                caption=onboarding_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Начать курс", callback_data="course_start")],
                    [InlineKeyboardButton("В меню", callback_data="go_menu")],
                ])
            )

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        await update.message.reply_text(f"Ошибка: {str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])
    await update.message.reply_text(
        "Команды:\n"
        "/start — начать или вернуться к курсу\n"
        "/menu — открыть меню\n"
        "/help — список команд",
        reply_markup=keyboard
    )


async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Временный обработчик для получения file_id картинок.
    Отправь боту любое фото — он ответит file_id, который можно вставить в modules.py.
    После того как все file_id получены — обработчик можно удалить.
    """
    photo = update.message.photo[-1]  # вариант с максимальным разрешением
    await update.message.reply_text(
        f"*file\\_id:*\n\n`{photo.file_id}`",
        parse_mode="Markdown"
    )


async def media_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает все нетекстовые сообщения.
    В режиме фидбэка — отклоняет с подсказкой «только текст».
    Для фото вне режимов — временно возвращает file_id (для настройки контента).
    """
    if context.user_data.get("feedback_mode"):
        # Удаляем медиа-сообщение из чата
        try:
            await update.message.delete()
        except Exception:
            pass
        # Удаляем предыдущую подсказку, чтобы не накапливать
        prev_hint = context.user_data.pop("feedback_hint_id", None)
        if prev_hint:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=prev_hint
                )
            except Exception:
                pass
        sent = await update.message.chat.send_message(
            "Принимается только текст. "
            "Ответь реплаем на сообщение выше — нажми на него и выбери «Ответить»."
        )
        context.user_data["feedback_hint_id"] = sent.message_id
        return

    # Вне режима фидбэка — для фото возвращаем file_id (временный инструмент)
    if update.message.photo:
        await get_file_id(update, context)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))

    # ── Навигация по урокам ───────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_step, pattern=r"^step_module_\d+_lesson_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_finish_lesson, pattern=r"^finish_module_\d+_lesson_\d+$"))
    app.add_handler(CallbackQueryHandler(show_module_intro, pattern=r"^module_intro_module_\d+$"))

    # ── Практика: точка входа и переходы между вопросами ─────────────────────
    # practice_module_01_lesson_01       → первый вопрос
    # practice_module_01_lesson_01_2     → вопрос с индексом 2
    app.add_handler(CallbackQueryHandler(handle_practice, pattern=r"^practice_module_\d+_lesson_\d+(_\d+)?$"))

    # ── CHOICE ────────────────────────────────────────────────────────────────
    # choice_answer_module_01_lesson_01_0_B
    app.add_handler(CallbackQueryHandler(handle_choice_answer, pattern=r"^choice_answer_module_\d+_lesson_\d+_\d+_[A-D]$"))

    # ── CASE ──────────────────────────────────────────────────────────────────
    # case_answer_module_01_lesson_01_0_A
    app.add_handler(CallbackQueryHandler(handle_case_answer, pattern=r"^case_answer_module_\d+_lesson_\d+_\d+_[A-D]$"))
    # case_retry_module_01_lesson_01_0
    app.add_handler(CallbackQueryHandler(handle_case_retry, pattern=r"^case_retry_module_\d+_lesson_\d+_\d+$"))
    # case_proceed_module_01_lesson_01_0
    app.add_handler(CallbackQueryHandler(handle_case_proceed, pattern=r"^case_proceed_module_\d+_lesson_\d+_\d+$"))

    # ── TRUE_FALSE ────────────────────────────────────────────────────────────
    # tf_answer_module_01_lesson_01_0_true
    app.add_handler(CallbackQueryHandler(handle_tf_answer, pattern=r"^tf_answer_module_\d+_lesson_\d+_\d+_(true|false)$"))

    # ── OPEN_REFLECT ──────────────────────────────────────────────────────────
    # reflect_submit_module_01_lesson_01_2
    app.add_handler(CallbackQueryHandler(handle_reflect_submit, pattern=r"^reflect_submit_module_\d+_lesson_\d+_\d+$"))
    # reflect_retry_module_01_lesson_01_2
    app.add_handler(CallbackQueryHandler(handle_reflect_retry, pattern=r"^reflect_retry_module_\d+_lesson_\d+_\d+$"))

    # ── AI-ассистент: точки входа и выхода ───────────────────────────────────
    # ai_enter                              → свободный вопрос из главного меню
    # ai_enter_module_01_lesson_01          → контекстный вопрос по уроку
    # ai_exit                               → выход из режима ассистента
    app.add_handler(CallbackQueryHandler(enter_ai_mode, pattern=r"^ai_enter$"))
    app.add_handler(CallbackQueryHandler(enter_ai_mode, pattern=r"^ai_enter_module_\d+_lesson_\d+$"))
    app.add_handler(CallbackQueryHandler(exit_ai_mode, pattern=r"^ai_exit$"))

    # ── Диспетчер текстовых сообщений ────────────────────────────────────────
    # Если активен ai_mode → handle_ai_message, иначе → handle_open_reflect_text.
    # Один MessageHandler избегает конфликта между двумя одинаковыми фильтрами.
    async def text_dispatcher(update, context):
        if context.user_data.get("ai_mode"):
            await handle_ai_message(update, context)
        elif context.user_data.get("feedback_mode"):
            await handle_feedback_text(update, context)
        else:
            await handle_open_reflect_text(update, context)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_dispatcher))

    # ── PHOTO_QUIZ ────────────────────────────────────────────────────────────
    # pq_answer_module_01_lesson_01_0_C
    app.add_handler(CallbackQueryHandler(handle_pq_answer, pattern=r"^pq_answer_module_\d+_lesson_\d+_\d+_[A-D]$"))

    # ── Нетекстовые сообщения: фидбэк-режим или временный file_id ────────────
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, media_dispatcher))

    # ── Меню ──────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^(course_start|progress|feedback|go_menu|about)$"))
    app.add_handler(CallbackQueryHandler(handle_reset_confirm, pattern="^reset_confirm$"))
    app.add_handler(CallbackQueryHandler(handle_reset_do, pattern="^reset_do$"))

    print("Бот запущен. Нажми Ctrl+C чтобы остановить.")
    app.run_polling()


if __name__ == "__main__":
    main()