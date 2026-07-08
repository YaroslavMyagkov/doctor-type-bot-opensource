# Общие вспомогательные функции для обработчиков

from telegram.error import BadRequest


async def safe_edit(query, text, reply_markup=None, parse_mode="Markdown") -> int:
    """
    Редактирует текст сообщения. Возвращает message_id итогового сообщения.

    - "Message is not modified" + разные клавиатуры → обновляем только keyboard.
    - Фото-сообщение или удалённое сообщение → удаляем и отправляем новое.
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return query.message.message_id
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            if reply_markup is not None:
                try:
                    await query.edit_message_reply_markup(reply_markup=reply_markup)
                except Exception:
                    pass
            return query.message.message_id
        # Фото-сообщение или недоступное — удаляем (игнорируем ошибку) и шлём заново
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await query.message.chat.send_message(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return sent.message_id
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await query.message.chat.send_message(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return sent.message_id


async def cleanup_lesson_photos(context, bot, chat_id: int):
    """
    Удаляет все фото-сообщения, которые бот разместил как иллюстрации к шагу.
    Ключи в user_data: step_photo_msg_id.
    """
    for key in ("step_photo_msg_id",):
        msg_id = context.user_data.pop(key, None)
        if msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
