# Навигация по урокам — шаги, переходы между уроками и модулями
# Практика вынесена в handlers/practice.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from content.modules import MODULES, get_module, get_lesson, get_next_lesson
from content.md_loader import get_step_text, get_step_image, get_practice_length
from storage.sheets import update_student, complete_lesson, complete_practice
from datetime import date
from handlers._helpers import safe_edit, cleanup_lesson_photos


def build_step_navigation(step: int, total_steps: int, module_id: str, lesson_id: str, has_practice: bool):
    """
    Строит кнопки навигации для шага урока.
    На последнем шаге:
      — если есть практика, кнопка ведёт в практику
      — если практики нет (заглушка), кнопка сразу завершает урок
    Дополнительно на каждом шаге доступна кнопка "Спросить по этому уроку" — режим AI-ассистента.
    """
    nav_row = []
    if step > 0:
        nav_row.append(InlineKeyboardButton("← Назад", callback_data=f"step_{module_id}_{lesson_id}_{step - 1}"))
    else:
        nav_row.append(InlineKeyboardButton("← К введению", callback_data=f"module_intro_{module_id}"))
    if step < total_steps - 1:
        nav_row.append(InlineKeyboardButton("Вперёд →", callback_data=f"step_{module_id}_{lesson_id}_{step + 1}"))
    else:
        # Последний шаг
        if has_practice:
            nav_row.append(InlineKeyboardButton("К практике →", callback_data=f"practice_{module_id}_{lesson_id}"))
        else:
            nav_row.append(InlineKeyboardButton("Завершить урок →", callback_data=f"finish_{module_id}_{lesson_id}"))

    ask_row = [InlineKeyboardButton(
        "Спросить по этому уроку",
        callback_data=f"ai_enter_{module_id}_{lesson_id}"
    )]
    menu_row = [InlineKeyboardButton("В меню", callback_data="go_menu")]
    return InlineKeyboardMarkup([nav_row, ask_row, menu_row])


async def show_module_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает вводный экран модуля"""
    query = update.callback_query
    await query.answer()

    # callback_data: "module_intro_module_01"
    module_id = query.data.replace("module_intro_", "")
    module = get_module(module_id)

    if not module:
        await safe_edit(query, "Модуль не найден.")
        return

    # Сбрасываем шаг — пользователь начнёт первый урок модуля с шага 0
    user_id = query.from_user.id
    first_lesson_id = module["lessons"][0]["id"]
    update_student(user_id,
        current_module=module_id,
        current_lesson=first_lesson_id,
        current_step="0",
        last_seen=str(date.today())
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Начать модуль →",
            callback_data=f"step_{module_id}_{first_lesson_id}_0")],
        [InlineKeyboardButton("В меню", callback_data="go_menu")]
    ])

    # Удаляем фото предыдущего шага (если было)
    await cleanup_lesson_photos(context, context.bot, query.message.chat_id)

    intro_image = module.get("intro_image")
    if intro_image:
        await query.message.delete()
        await query.message.chat.send_photo(
            photo=intro_image,
            caption=module["intro"],
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await safe_edit(
            query,
            text=module["intro"],
            reply_markup=keyboard
        )


async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает навигацию по шагам урока"""
    query = update.callback_query
    await query.answer()

    # callback_data: "step_module_01_lesson_01_2"
    parts = query.data.split("_")
    module_id = f"{parts[1]}_{parts[2]}"
    lesson_id = f"{parts[3]}_{parts[4]}"
    step = int(parts[5])

    lesson = get_lesson(module_id, lesson_id)
    if not lesson:
        await safe_edit(query, "Урок не найден.")
        return

    total_steps = len(lesson["steps"])

    # Защита от выхода за границы (на случай старых данных в Sheets)
    if step >= total_steps:
        step = total_steps - 1
    if step < 0:
        step = 0

    step_data = lesson["steps"][step]
    has_practice = get_practice_length(module_id, lesson_id) > 0

    # Обновляем прогресс в Sheets
    user_id = query.from_user.id
    update_student(user_id,
        current_module=module_id,
        current_lesson=lesson_id,
        current_step=str(step),
        last_seen=str(date.today())
    )

    # Помечаем урок как просмотренный когда студент дошёл до последнего шага
    if step == total_steps - 1:
        complete_lesson(user_id, lesson_id)

    caption = f"*{lesson['title']}* · шаг {step + 1} из {total_steps}\n\n"
    step_text = get_step_text(module_id, lesson_id, step)
    nav_keyboard = build_step_navigation(step, total_steps, module_id, lesson_id, has_practice)
    image_file_id = get_step_image(module_id, lesson_id, step)

    # Удаляем фото предыдущего шага (если было)
    await cleanup_lesson_photos(context, context.bot, query.message.chat_id)

    if image_file_id:
        # Порядок: фото выше → текст с кнопками ниже.
        # Удаляем старое nav-сообщение, отправляем фото, потом текст.
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
        await safe_edit(
            query,
            text=caption + step_text,
            reply_markup=nav_keyboard
        )


async def handle_finish_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает урок, обновляет прогресс, показывает что дальше"""
    query = update.callback_query
    await query.answer()

    # callback_data: "finish_module_01_lesson_01"
    parts = query.data.split("_")
    module_id = f"{parts[1]}_{parts[2]}"
    lesson_id = f"{parts[3]}_{parts[4]}"

    user_id = query.from_user.id
    module = get_module(module_id)
    lesson = get_lesson(module_id, lesson_id)

    all_module_lessons = [l["id"] for l in module["lessons"]]
    complete_practice(user_id, lesson_id, module_id, all_module_lessons)

    next_lesson = get_next_lesson(module_id, lesson_id)

    # Удаляем фото предыдущего шага
    await cleanup_lesson_photos(context, context.bot, query.message.chat_id)
    finish_image = lesson.get("finish_image") if lesson else None

    # Собираем текст и клавиатуру — вся логика ветвления здесь
    if next_lesson is None:
        # Курс пройден
        finish_text = "Курс пройден.\n\nЭто было непросто, но ты справился."
        finish_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("В меню", callback_data="go_menu")]
        ])
    else:
        next_module_id, next_lesson_id = next_lesson

        # Сбрасываем шаг — следующий урок начнётся с нуля.
        update_student(user_id,
            current_module=next_module_id,
            current_lesson=next_lesson_id,
            current_step="0",
            last_seen=str(date.today())
        )

        if next_module_id != module_id:
            # Следующий урок — в новом модуле
            next_module = get_module(next_module_id)
            finish_text = f"Урок завершён.\n\nДальше — *{next_module['title']}*."
            finish_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Начать {next_module['title']}",
                    callback_data=f"module_intro_{next_module_id}")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")]
            ])
        else:
            # Следующий урок — в том же модуле
            next_lesson_data = get_lesson(next_module_id, next_lesson_id)
            finish_text = f"Урок завершён.\n\nСледующий: *{next_lesson_data['title']}*."
            finish_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Следующий урок →",
                    callback_data=f"step_{next_module_id}_{next_lesson_id}_0")],
                [InlineKeyboardButton("В меню", callback_data="go_menu")]
            ])

    # Показываем экран финиша — с картинкой (caption) или без
    if finish_image:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_photo(
            photo=finish_image,
            caption=finish_text,
            reply_markup=finish_keyboard,
            parse_mode="Markdown"
        )
    else:
        await safe_edit(query, text=finish_text, reply_markup=finish_keyboard)
