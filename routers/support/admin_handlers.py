from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from config import SUPPORT_CHAT_ID
from db_logic.repository import SupportTicketsRepo
from app import storage
from states import SupportState
from aiogram import Router

router = Router()

SERVICE_TYPES = {
    "pinned_message",
    "new_chat_members",
    "left_chat_member",
    "new_chat_title",
    "new_chat_photo",
    "delete_chat_photo",
    "group_chat_created",
    "supergroup_chat_created",
    "channel_chat_created",
    "message_auto_delete_timer_changed",
    "forum_topic_created",
    "forum_topic_edited",
    "forum_topic_closed",
    "forum_topic_reopened",
    "general_forum_topic_hidden",
    "general_forum_topic_unhidden",
}




# выводить chat_id при добавлении в новую группу
@router.message(F.new_chat_members)
async def new_chat_member(message: types.Message):
    await message.reply(f"ID чата для .env: {message.chat.id}\n"
                        f"Не забудьте сделать бота администратором!")


@router.message(F.chat.id == SUPPORT_CHAT_ID)
async def support_admin_reply(message: types.Message):
    if message.content_type in SERVICE_TYPES: # Проверка на системное сообщение
        return

    message_thread_id = message.message_thread_id
    if not message_thread_id:
        return  # сообщение не в топике

    ticket = SupportTicketsRepo.get_open_by_thread_id(message_thread_id)

    if not ticket:
        await message.reply("Тикет не найден")
        return

    # FSM контекст для пользователя тикета
    ctx = FSMContext(
        storage=storage,
        key=StorageKey(
            bot_id=message.bot.id,
            chat_id=ticket['chat_id'],
            user_id=ticket['tg_id'],
        ),
    )

    await ctx.set_state(SupportState.in_support)
    await ctx.update_data(message_thread_id=message_thread_id)

    try:
        await message.bot.copy_message(
            chat_id=ticket['chat_id'],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception as ex:
        await message.answer(f"Не удалось доставить сообщение пользователю: {ex}")


from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

@router.callback_query(F.data == "close_ticket")
async def close_ticket(call: types.CallbackQuery):
    message_thread_id = call.message.message_thread_id if call.message else None
    if not message_thread_id:
        await call.answer("Не в топике")
        return

    ticket = SupportTicketsRepo.get_open_by_thread_id(message_thread_id)
    if not ticket:
        # Можно считать идемпотентным закрытием:
        # тикет уже закрыт/удалён, а топика может не быть — не ошибка.
        await call.answer("Тикет уже закрыт или не найден")
        # и всё равно попробуем удалить топик на всякий случай
        try:
            await call.bot.delete_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=message_thread_id,
            )
        except (TelegramBadRequest, TelegramAPIError):
            pass
        return

    # 1) очистить FSM (лучше не давать этому ронять закрытие)
    try:
        ctx = FSMContext(
            storage=storage,
            key=StorageKey(
                bot_id=call.bot.id,
                chat_id=ticket["chat_id"],
                user_id=ticket["tg_id"],
            ),
        )
        await ctx.clear()
    except Exception:
        pass

    # 2) уведомить пользователя (тоже best effort)
    try:
        await call.bot.send_message(
            chat_id=ticket["chat_id"],
            text="Ваш запрос был закрыт, для открытия нового отправьте /start",
        )
    except Exception:
        pass

    # 3) ВСЕГДА закрыть тикет в БД
    try:
        SupportTicketsRepo.close_by_thread_id(message_thread_id)
    except Exception:
        # в идеале логировать, но не валить обработчик
        pass

    # 4) удалить топик (best effort)
    try:
        await call.bot.delete_forum_topic(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=message_thread_id,
        )
    except (TelegramBadRequest, TelegramAPIError):
        pass

    await call.answer("Тикет закрыт ✅")

