from aiogram import types
from pydantic import BaseModel

from config import SUPPORT_CHAT_ID
from db_logic.base import SupportTickets, AllTickets
from loader import dp
from states import SupportState


class SupportRequest(BaseModel):
    user_id: int
    username: str | None
    full_name: str | None
    message_id: int

    async def send_support_request(self):
        _close_support_request_kb = types.InlineKeyboardMarkup()
        _close_support_request_kb.add(
            types.InlineKeyboardButton(
                text="Закрыть тикет", callback_data="close_ticket"
            )
        )
        AllTickets().create_ticket(self.user_id)
        id_last_ticket = AllTickets().get_ticket_by_tg_id(self.user_id).id
        message_thread_id = await self._create_forum_topic(id_last_ticket)

        # Создаёт запись в базе данных о новом обращении
        SupportTickets().create_ticket(self.user_id, message_thread_id)


        await dp.bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=message_thread_id,
            text=f"Новое обращение в тех. поддержку от пользователя {self.user_id} @{self.username}",
            reply_markup=_close_support_request_kb,
        )
        await dp.bot.forward_message(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=message_thread_id,
            from_chat_id=self.user_id,
            message_id=self.message_id,
        )



        # ticket = SupportTickets().get_ticket_by_message_thread_id(message_thread_id)
        # user_state = dp.current_state(chat=ticket.tg_id, user=ticket.tg_id)
        # await user_state.set_state(SupportState.in_support)
        # await user_state.update_data(message_thread_id=message_thread_id)

    # Создаёт топик и возвращает его id
    async def _create_forum_topic(self, last_ticket_id=0):
        return (
            await dp.bot.create_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                name=f"𒊹{self.full_name or ''} | {self.username or self.user_id} #{last_ticket_id or 0}",
            )
        ).message_thread_id



