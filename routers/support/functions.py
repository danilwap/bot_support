from __future__ import annotations

from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SUPPORT_CHAT_ID
from db_logic.repository import SupportTicketsRepo


class SupportRequest(BaseModel):
    user_id: int
    chat_id: int  # ✅ было нужно (ты используешь self.chat_id)
    username: str | None = None
    full_name: str | None = None
    message_id: int

    async def send_support_request(self, bot: Bot) -> None:
        # 0) проверяем: есть ли уже активный тикет на пользователя
        existing = SupportTicketsRepo.get_open_by_tg_id(self.user_id)

        if existing:
            sent = None
            try:
                sent = await bot.forward_message(
                    chat_id=SUPPORT_CHAT_ID,
                    from_chat_id=self.chat_id,
                    message_id=self.message_id,
                    message_thread_id=existing["thread_id"],
                )
            except (TelegramBadRequest, TelegramAPIError):
                sent = None

            # если улетело в general — считаем тикет битым
            ok_in_topic = bool(getattr(sent, "is_topic_message", False))

            if ok_in_topic:
                return

            # удаляем мусор из general (если отправилось)
            if sent:
                try:
                    await bot.delete_message(SUPPORT_CHAT_ID, sent.message_id)
                except Exception:
                    pass

            # удаляем битый тикет из БД
            SupportTicketsRepo.close_by_tg_id(self.user_id)
            # дальше создаём новый топик

        # 1) создаём топик
        topic = await bot.create_forum_topic(
            chat_id=SUPPORT_CHAT_ID,
            name=f"{self.full_name or ''}".strip() or "Без имени",
        )
        thread_id = topic.message_thread_id

        # 2) создаём запись в support_tickets
        ticket_id = SupportTicketsRepo.create_ticket(
            tg_id=self.user_id,
            thread_id=thread_id,
            chat_id=self.chat_id,
        )

        # 3) переименовываем топик с номером
        try:
            await bot.edit_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=thread_id,
                name=f"{self.full_name or ''} | {self.username or self.user_id} #{ticket_id}",
            )
        except Exception as e:
            logger.warning(
                f"Не удалось переименовать топик {thread_id}: {e}"
            )

        # 4) кнопка "Закрыть тикет" (aiogram 3 builder)
        kb = InlineKeyboardBuilder()
        kb.button(text="Закрыть тикет", callback_data="close_ticket")
        kb = kb.as_markup()

        # 5) пишем в топик и форвардим исходное сообщение
        uname = f"@{self.username}" if self.username else "без username"
        msg = await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=thread_id,
            text=f"Новое обращение в тех. поддержку от пользователя {self.user_id} ({uname})",
            reply_markup=kb,
        )
        await bot.pin_chat_message(chat_id=SUPPORT_CHAT_ID,
                                   message_id=msg.message_id,
                                   disable_notification=True, )

        await bot.forward_message(
            chat_id=SUPPORT_CHAT_ID,
            from_chat_id=self.chat_id,
            message_id=self.message_id,
            message_thread_id=thread_id,
        )
