from aiogram import types
from aiogram.dispatcher import FSMContext

from config import SUPPORT_CHAT_ID
from db_logic.base import SupportTickets, AllTickets
from handlers.support.functions import SupportRequest
from loader import dp
from states import SupportState


@dp.message_handler(commands=["start", "support", "help"])
async def main_command(message: types.Message):
    await message.reply(
        text="Добро пожаловать в поддержку. Введите сообщение для отправки.",
    )
    await SupportState.send_request.set()


@dp.message_handler(
    state=SupportState.send_request, content_types=types.ContentType.ANY
)
async def send_request(message: types.Message, state: FSMContext):
    support_request = SupportRequest(
        user_id=message.from_user.id,
        username=message.from_user.username,
        message_id=message.message_id,
        full_name=message.from_user.full_name,
    )
    await support_request.send_support_request()
    await message.reply(text="Ваше сообщение отправлено. Ожидайте ответа.")
    await state.set_state(SupportState.in_support)


@dp.message_handler(state=SupportState.in_support, content_types=types.ContentType.ANY)
async def support_reply(message: types.Message, state: FSMContext):
    try:
        state_data = await state.get_data()
        message_thread_id = SupportTickets.get_ticket_by_tg_id(message.chat.id).message_thread_id
        await dp.bot.forward_message(
            from_chat_id=message.chat.id,
            message_thread_id=message_thread_id,
            chat_id=SUPPORT_CHAT_ID,
            message_id=message.message_id,
        )
    except Exception as e:
        await send_request(message, SupportState.send_request)

@dp.message_handler(commands=["test"])
async def test(message: types.Message):
    AllTickets.create_ticket(message.from_user.id)
    print(AllTickets.get_ticket_by_tg_id(message.chat.id).id)

    # try:
    #     await dp.bot.send_message(chat_id=SUPPORT_CHAT_ID, message_thread_id=329, text="test")
    # except Exception as e:
    #     await dp.bot.create_forum_topic(
    #         chat_id=SUPPORT_CHAT_ID,
    #         name=f"test",
    #     )