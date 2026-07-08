# Главное меню и обработчик кнопок меню

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from content.modules import MODULES
from handlers._helpers import safe_edit, cleanup_lesson_photos
from handlers._images import MENU_IMAGE_ID, RESET_IMAGE_ID, FEEDBACK_IMAGE_ID, FEEDBACK_THANKS_IMAGE_ID
from storage.sheets import save_feedback


def build_main_menu():
    """Строит клавиатуру главного меню"""
    keyboard = [
        [InlineKeyboardButton("Продолжить курс", callback_data="course_start")],
        [InlineKeyboardButton("Мой прогресс", callback_data="progress")],
        [InlineKeyboardButton("Спросить ассистента", callback_data="ai_enter")],
        [InlineKeyboardButton("О боте", callback_data="about")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню по команде /menu. Сбрасывает режим ассистента."""
    from handlers.ai import reset_ai_state
    reset_ai_state(context, user_id=update.effective_user.id)

    await update.message.chat.send_photo(
        photo=MENU_IMAGE_ID,
        caption="Меню:",
        reply_markup=build_main_menu()
    )


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки меню"""
    query = update.callback_query
    await query.answer()

    if query.data == "course_start":
        from storage.sheets import get_or_create_student
        from content.modules import get_next_lesson, get_lesson, get_module

        user_id = query.from_user.id
        username = query.from_user.username or "unknown"
        student = get_or_create_student(user_id, username)

        module_id = student.get("current_module", "module_01")
        lesson_id = student.get("current_lesson", "lesson_01")
        current_step = int(student.get("current_step", 0))
        completed_practice = [l for l in student.get("completed_practice", "").split(",") if l]
        practice_step = student.get("current_practice_step", "")

        # Сценарий 1: студент остановился в практике — возвращаем к нужному вопросу
        if practice_step != "":
            q_index = int(practice_step)
            lesson_data = get_lesson(module_id, lesson_id)
            lesson_title = lesson_data["title"] if lesson_data else lesson_id
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Продолжить практику",
                    callback_data=f"practice_{module_id}_{lesson_id}_{q_index}")],
                [InlineKeyboardButton("К уроку",
                    callback_data=f"step_{module_id}_{lesson_id}_0")]
            ])
            await safe_edit(
                query,
                text=f"Ты остановился на практике урока *{lesson_title}*, "
                     f"вопрос {q_index + 1}.\n\nПродолжим?",
                reply_markup=keyboard
            )
            return

        # Сценарий 2: текущий урок завершён — переходим к следующему
        if lesson_id in completed_practice:
            next_lesson = get_next_lesson(module_id, lesson_id)

            if next_lesson is None:
                # Курс пройден полностью
                await safe_edit(
                    query,
                    text="Курс пройден.\n\n"
                         "Если хочешь повторить какой-то урок — открой «Мой прогресс».",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("В меню", callback_data="go_menu")]
                    ])
                )
                return

            next_module_id, next_lesson_id = next_lesson

            if next_module_id != module_id:
                # Следующий урок — в новом модуле. Показываем интро модуля.
                next_module = get_module(next_module_id)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"Начать {next_module['title']}",
                        callback_data=f"module_intro_{next_module_id}")],
                    [InlineKeyboardButton("В меню", callback_data="go_menu")]
                ])
                await safe_edit(
                    query,
                    text=f"Модуль пройден. Дальше — *{next_module['title']}*.",
                    reply_markup=keyboard
                )
            else:
                # Следующий урок — в том же модуле
                next_lesson_data = get_lesson(next_module_id, next_lesson_id)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Продолжить",
                        callback_data=f"step_{next_module_id}_{next_lesson_id}_0")],
                    [InlineKeyboardButton("В меню", callback_data="go_menu")]
                ])
                await safe_edit(
                    query,
                    text=f"Следующий урок: *{next_lesson_data['title']}*.",
                    reply_markup=keyboard
                )
            return

        # Сценарий 3a: совсем новый пользователь — сразу открываем первый шаг урока
        completed_lessons = student.get("completed_lessons", "")
        if not completed_lessons and current_step == 0 and not completed_practice:
            from storage.sheets import update_student as _update
            from datetime import date as _date
            from content.md_loader import get_step_text, get_step_image, get_practice_length
            from handlers.course import build_step_navigation
            from content.modules import get_lesson as _get_lesson

            first_module = MODULES[0]
            first_lesson_id = first_module["lessons"][0]["id"]
            first_module_id = first_module["id"]
            _update(user_id,
                current_module=first_module_id,
                current_lesson=first_lesson_id,
                current_step="0",
                last_seen=str(_date.today())
            )

            lesson_obj = _get_lesson(first_module_id, first_lesson_id)
            total_steps = len(lesson_obj["steps"])
            has_practice = get_practice_length(first_module_id, first_lesson_id) > 0
            caption = f"*{lesson_obj['title']}* · шаг 1 из {total_steps}\n\n"
            step_text = get_step_text(first_module_id, first_lesson_id, 0)
            nav_keyboard = build_step_navigation(0, total_steps, first_module_id, first_lesson_id, has_practice)
            image_file_id = get_step_image(first_module_id, first_lesson_id, 0)

            await cleanup_lesson_photos(context, context.bot, query.message.chat_id)
            if image_file_id:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                photo_msg = await query.message.chat.send_photo(photo=image_file_id)
                context.user_data["step_photo_msg_id"] = photo_msg.message_id
                await query.message.chat.send_message(
                    text=caption + step_text,
                    reply_markup=nav_keyboard,
                    parse_mode="Markdown"
                )
            else:
                await safe_edit(query, text=caption + step_text, reply_markup=nav_keyboard)
            return

        # Сценарий 3b: студент читает урок — возвращаем к текущему шагу
        lesson_data = get_lesson(module_id, lesson_id)
        lesson_title = lesson_data["title"] if lesson_data else lesson_id

        # Защита от выхода за границы шагов (бывает после ручных правок в Sheets)
        if lesson_data:
            current_step = min(current_step, len(lesson_data["steps"]) - 1)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Продолжить",
                callback_data=f"step_{module_id}_{lesson_id}_{current_step}")],
            [InlineKeyboardButton("В меню", callback_data="go_menu")]
        ])
        await safe_edit(
            query,
            text=f"Продолжаем: *{lesson_title}*.",
            reply_markup=keyboard
        )

    elif query.data == "progress":
        from storage.sheets import get_or_create_student
        user_id = query.from_user.id
        username = query.from_user.username or "unknown"
        student = get_or_create_student(user_id, username)

        completed_practice = [l for l in student.get("completed_practice", "").split(",") if l]
        completed_modules = [m for m in student.get("completed_modules", "").split(",") if m]
        current_lesson_id = student.get("current_lesson", "")

        lines = ["*Твой прогресс*\n"]
        keyboard = []

        for module in MODULES:
            module_done = module["id"] in completed_modules
            module_marker = "✓" if module_done else "·"
            lines.append(f"{module_marker} *{module['title']}*")

            for lesson in module["lessons"]:
                if lesson["id"] in completed_practice:
                    lines.append(f"    ✓ {lesson['title']}")
                    keyboard.append([InlineKeyboardButton(
                        f"Перейти: {lesson['title']}",
                        callback_data=f"step_{module['id']}_{lesson['id']}_0"
                    )])
                elif lesson["id"] == current_lesson_id:
                    total = len(lesson["steps"])
                    current = int(student.get("current_step", 0)) + 1
                    lines.append(f"    · {lesson['title']} (шаг {current} из {total})")
                else:
                    lines.append(f"    · {lesson['title']}")

        keyboard.append([InlineKeyboardButton("Продолжить курс", callback_data="course_start")])
        keyboard.append([InlineKeyboardButton("⚠️ Сбросить прогресс", callback_data="reset_confirm")])
        keyboard.append([InlineKeyboardButton("В меню", callback_data="go_menu")])

        await safe_edit(
            query,
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "about":
        from handlers._images import ONBOARDING_IMAGE_ID
        about_text = (
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
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_photo(
            photo=ONBOARDING_IMAGE_ID,
            caption=about_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Оставить фидбэк", callback_data="feedback")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")],
            ])
        )

    elif query.data == "feedback":
        text = (
            "*Оставь фидбэк*\n\n"
            "Что можно написать:\n"
            "— что в уроках понятно, а что объяснено плохо\n"
            "— темы, которые хочется разобрать подробнее\n"
            "— баги или неудобства в навигации\n"
            "— что понравилось\n"
            "— предложения по улучшению курса\n"
            "— вопросы, на которые пока нет ответа в материале\n\n"
            "_Ответь реплаем на это сообщение: нажми на него и выбери «Ответить». "
            "Принимается только текст._"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("В меню", callback_data="go_menu")]
        ])
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await query.message.chat.send_photo(
            photo=FEEDBACK_IMAGE_ID,
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        context.user_data["feedback_mode"] = {"message_id": sent.message_id}

    elif query.data == "go_menu":
        # Удаляем плавающее фото урока/практики (если висит в чате)
        await cleanup_lesson_photos(context, context.bot, query.message.chat_id)

        # Перед сбросом state — забираем ID-шники подсказок и ошибочных сообщений,
        # чтобы успеть их удалить из чата (reset_ai_state иначе очистит словарь)
        hint_id = context.user_data.get("open_reflect_hint_id")
        wrong_ids = context.user_data.get("open_reflect_wrong_ids", [])
        fb_hint_id = context.user_data.get("feedback_hint_id")
        fb_wrong_ids = context.user_data.get("feedback_wrong_ids", [])

        # Полный сброс всех режимов — никакого мусора в user_data
        from handlers.ai import reset_ai_state
        reset_ai_state(context, user_id=query.from_user.id)

        # Чистим хвосты из чата
        all_cleanup = (
            ([hint_id] if hint_id else []) + wrong_ids +
            ([fb_hint_id] if fb_hint_id else []) + fb_wrong_ids
        )
        for msg_id in all_cleanup:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=msg_id
                )
            except Exception:
                pass

        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_photo(
            photo=MENU_IMAGE_ID,
            caption="Меню:",
            reply_markup=build_main_menu()
        )


async def handle_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран подтверждения сброса прогресса."""
    query = update.callback_query
    await query.answer()

    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.chat.send_photo(
        photo=RESET_IMAGE_ID,
        caption="Сбросить весь прогресс?\n\nВсе пройденные уроки и практики будут удалены. Курс начнётся заново.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Да, сбросить", callback_data="reset_do")],
            [InlineKeyboardButton("Отмена", callback_data="progress")],
        ])
    )


async def handle_reset_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет сброс прогресса — обнуляет все поля студента."""
    query = update.callback_query
    await query.answer()

    from storage.sheets import update_student
    from content.modules import MODULES

    user_id = query.from_user.id
    first_module_id = MODULES[0]["id"]

    update_student(
        user_id,
        current_module=first_module_id,
        current_lesson="lesson_01",
        current_step="0",
        current_practice_step="",
        completed_lessons="",
        completed_practice="",
        completed_modules="",
    )

    await safe_edit(
        query,
        text="Прогресс сброшен. Курс начнётся с самого начала.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Начать курс", callback_data="course_start")],
            [InlineKeyboardButton("В меню", callback_data="go_menu")],
        ])
    )


# ─── Фидбэк — обработчик текстового ответа ───────────────────────────────────

async def handle_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает текстовый реплай студента в режиме фидбэка.
    Логика аналогична OPEN_REFLECT: принимается только реплай на сообщение-вопрос.
    """
    feedback_data = context.user_data.get("feedback_mode")

    if not feedback_data:
        try:
            await update.message.delete()
        except Exception:
            pass
        return

    # Сообщение должно быть реплаем именно на сообщение с вопросом
    if not update.message.reply_to_message or \
       update.message.reply_to_message.message_id != feedback_data["message_id"]:
        # Удаляем предыдущую подсказку
        prev_hint = context.user_data.pop("feedback_hint_id", None)
        if prev_hint:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=prev_hint
                )
            except Exception:
                pass
        sent = await update.message.reply_text(
            "Чтобы фидбэк засчитался, нужно ответить реплаем "
            "на сообщение выше — нажми на него и выбери «Ответить»."
        )
        context.user_data["feedback_hint_id"] = sent.message_id
        context.user_data["feedback_wrong_ids"] = \
            context.user_data.get("feedback_wrong_ids", []) + [update.message.message_id]
        return

    # Корректный реплай — сохраняем фидбэк
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    feedback_text = update.message.text

    save_feedback(user_id, username, feedback_text)

    # Чистим state
    feedback_msg_id = feedback_data["message_id"]
    context.user_data.pop("feedback_mode", None)
    hint_id = context.user_data.pop("feedback_hint_id", None)
    wrong_ids = context.user_data.pop("feedback_wrong_ids", [])

    for msg_id in ([hint_id] if hint_id else []) + wrong_ids:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=msg_id
            )
        except Exception:
            pass

    # Удаляем сообщение-вопрос — его кнопка «В меню» уже устарела
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, message_id=feedback_msg_id
        )
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать ещё", callback_data="feedback")],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])
    await update.message.chat.send_photo(
        photo=FEEDBACK_THANKS_IMAGE_ID,
        caption="Спасибо за фидбэк — это помогает сделать курс лучше.",
        reply_markup=keyboard
    )
