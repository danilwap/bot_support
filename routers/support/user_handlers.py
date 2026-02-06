from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SUPPORT_CHAT_ID
from db_logic.repository import SupportTicketsRepo
from routers.support.functions import SupportRequest
from states import SupportState
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from functools import wraps
from aiogram import types, Router, F

from typing import Any, Awaitable, Callable, Optional, Union

from aiogram.types import Message, CallbackQuery

from db_logic.repository import UsersRepo

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from typing import Dict

# Блокировка против гонок
_user_locks: Dict[int, asyncio.Lock] = {}
def get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


async def ensure_topic_and_forward(
    *,
    bot,
    message: types.Message,
    ticket: dict,
) -> int:
    """Гарантирует, что сообщение попадёт в топик, а не в general.
    Возвращает актуальный thread_id.
    """
    thread_id = ticket["thread_id"]

    sent = await bot.forward_message(
        chat_id=SUPPORT_CHAT_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        message_thread_id=thread_id,
    )

    # Если thread не применился — улетело в general
    if getattr(sent, "is_topic_message", False):
        return thread_id

    # 1) убрать мусор из general
    try:
        await bot.delete_message(SUPPORT_CHAT_ID, sent.message_id)
    except Exception:
        pass

    # 2) восстановить топик и обновить thread_id тикета
    topic = await bot.create_forum_topic(
        chat_id=SUPPORT_CHAT_ID,
        name=(message.from_user.full_name or "").strip() or "Без имени",
    )
    new_thread_id = topic.message_thread_id

    ticket_id = ticket["id"]
    try:
        await bot.edit_forum_topic(
            chat_id=SUPPORT_CHAT_ID,
            message_thread_id=new_thread_id,
            name=f"{message.from_user.full_name or ''} | "
                 f"{message.from_user.username or message.from_user.id} #{ticket_id}",
        )
    except Exception:
        pass

    ok = SupportTicketsRepo.update_thread_id(ticket_id=ticket_id, new_thread_id=new_thread_id)
    if not ok:
        # тикет уже закрыли/удалили в параллели
        raise RuntimeError("ticket_closed")

    # (опционально) кнопка + pinned сообщение как у тебя
    kb = InlineKeyboardBuilder()
    kb.button(text="Закрыть тикет", callback_data="close_ticket")
    kb = kb.as_markup()

    uname = f"@{message.from_user.username}" if message.from_user.username else "без username"
    msg = await bot.send_message(
        chat_id=SUPPORT_CHAT_ID,
        message_thread_id=new_thread_id,
        text=f"Восстановлено обращение от пользователя {message.from_user.id} ({uname})",
        reply_markup=kb,
    )
    try:
        await bot.pin_chat_message(
            chat_id=SUPPORT_CHAT_ID,
            message_id=msg.message_id,
            disable_notification=True,
        )
    except Exception:
        pass

    # 3) переслать исходное сообщение уже в восстановленный топик
    await bot.forward_message(
        chat_id=SUPPORT_CHAT_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        message_thread_id=new_thread_id,
    )

    return new_thread_id



def privacy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Политика конфиденциальности",
                    url="https://helloanker.ru/privacy-policy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📑 Согласие на обработку персональных данных",
                    url="https://helloanker.ru/personal-data",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Согласен(на) на обработку персональных данных",
                    callback_data="accept_privacy",
                )
            ]
        ]
    )


router = Router()

AiogramEvent = Union[Message, CallbackQuery]
Handler = Callable[..., Awaitable[Any]]


def require_privacy(handler: Handler) -> Handler:
    @wraps(handler)
    async def wrapper(event: AiogramEvent, *args: Any, **kwargs: Any) -> Any:
        # извлекаем tg_id
        if isinstance(event, Message):
            tg_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            tg_id = event.from_user.id if event.from_user else None
        else:
            tg_id = None

        if tg_id is None:
            return

        # гарантируем наличие пользователя
        UsersRepo.get_or_create(tg_id)

        if not UsersRepo.has_privacy(tg_id):
            text = (
                "Для использования чат-бота вам необходимо подтвердить согласие "
                "на обработку персональных данных в соответствии с политикой "
                "конфиденциальности\n\n"
                "https://helloanker.ru/privacy-policy\n"
                "https://helloanker.ru/personal-data"
            )

            if isinstance(event, CallbackQuery):
                # закрываем "часики"
                try:
                    await event.answer()
                except Exception:
                    pass

                if event.message:
                    await event.message.answer(text, reply_markup=privacy_kb())
            else:
                await event.answer(text, reply_markup=privacy_kb())

            return  # ⛔ дальше хендлер НЕ выполняется

        return await handler(event, *args, **kwargs)

    return wrapper


# Декоратор проверяет тип чат, если группа, то не отправляет
def private_only(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        chat = None

        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat

        # если не смогли определить чат — просто не обрабатываем
        if chat is None:
            return

        if chat.type != ChatType.PRIVATE:
            # для callback можно ещё закрыть "часики"
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
            return

        return await handler(event, *args, **kwargs)

    return wrapper



@router.message(Command("start", "support", "help"))
@private_only
@require_privacy
async def main_command(message: types.Message, state: FSMContext):
    await message.reply(
        text="Добро пожаловать в поддержку. Введите сообщение для отправки.",
    )
    await state.set_state(SupportState.send_request)


@router.message(SupportState.send_request)
@private_only
@require_privacy
async def send_request(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lock = get_user_lock(user_id)

    async with lock:
        ticket = SupportTicketsRepo.get_open_by_tg_id(user_id)

        if ticket and ticket.get("thread_id"):
            await state.set_state(SupportState.in_support)
            try:
                await ensure_topic_and_forward(bot=message.bot, message=message, ticket=ticket)
                await message.reply("Ваше сообщение отправлено. Ожидайте ответа.")
                return
            except RuntimeError:
                # ticket_closed
                await state.set_state(SupportState.send_request)
                await message.answer("Тикет уже закрыт. Напишите сообщение для нового обращения.")
                return
            except (TelegramBadRequest, TelegramAPIError):
                # если именно API-ошибка — закрываем и создаём новый ниже
                SupportTicketsRepo.close_by_thread_id(ticket["thread_id"])
                await state.set_state(SupportState.send_request)
                # падаем дальше в создание нового

        # новый тикет обычным путём
        support_request = SupportRequest(
            user_id=user_id,
            username=message.from_user.username,
            message_id=message.message_id,
            full_name=message.from_user.full_name,
            chat_id=message.chat.id
        )
        await support_request.send_support_request(message.bot)
        await state.set_state(SupportState.in_support)

    await message.reply("Ваше сообщение отправлено. Ожидайте ответа.")



@router.message(SupportState.in_support)
@private_only
@require_privacy
async def support_reply(message: types.Message, state: FSMContext):
    ticket = SupportTicketsRepo.get_open_by_tg_id(message.from_user.id)
    message_thread_id = ticket['thread_id'] if ticket else None

    if not message_thread_id:
        await state.set_state(SupportState.send_request)
        await message.answer("Ваш тикет был закрыт. Напишите сообщение для нового обращения.")
        return

    try:
        sent = await message.bot.forward_message(
            chat_id=SUPPORT_CHAT_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=message_thread_id,
        )

        # ✅ ДЕТЕКТОР: если thread не применился — Telegram отправил в general
        # у "правильного" сообщения будет sent.message_thread_id и sent.is_topic_message == True
        if not getattr(sent, "is_topic_message", False):
            # 1) удалить мусор из general
            try:
                await message.bot.delete_message(SUPPORT_CHAT_ID, sent.message_id)
            except Exception:
                pass

            # 2) восстановить топик для ЭТОГО ЖЕ ticket_id (номер сохраняется)
            # создаём новый топик
            topic = await message.bot.create_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                name=f"{message.from_user.full_name or ''}".strip() or "Без имени",
            )
            new_thread_id = topic.message_thread_id

            ticket_id = ticket['id']

            # переименовываем с тем же #ticket_id
            try:
                await message.bot.edit_forum_topic(
                    chat_id=SUPPORT_CHAT_ID,
                    message_thread_id=new_thread_id,
                    name=f"{message.from_user.full_name or ''} | {message.from_user.username or message.from_user.id} #{ticket_id}",
                )
            except Exception:
                pass

            # обновляем thread_id у существующего тикета
            ok = SupportTicketsRepo.update_thread_id(ticket_id=ticket_id, new_thread_id=new_thread_id)
            if not ok:
                # тикет уже закрыт/удалён — просим пользователя открыть новый
                await state.set_state(SupportState.send_request)
                await message.answer("Тикет уже закрыт. Напишите сообщение для нового обращения.")
                return

            # 2.1) кнопка "Закрыть тикет" (aiogram 3 builder)
            kb = InlineKeyboardBuilder()
            kb.button(text="Закрыть тикет", callback_data="close_ticket")
            kb = kb.as_markup()

            # 2.2) пишем в топик и форвардим исходное сообщение
            uname = f"@{message.from_user.username}" if message.from_user.username else "без username"
            msg = await message.bot.send_message(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=new_thread_id,
                text=f"Восстановлено обращение в тех. поддержку от пользователя {message.from_user.id} ({uname})",
                reply_markup=kb,
            )

            await message.bot.pin_chat_message(chat_id=SUPPORT_CHAT_ID,
                                       message_id=msg.message_id,
                                       disable_notification=True, )


            # 3) СРАЗУ повторно пересылаем сообщение в восстановленный топик
            await message.bot.forward_message(
                chat_id=SUPPORT_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=new_thread_id,
            )

            # 4) возвращаем пользователя в in_support
            await state.set_state(SupportState.in_support)

            # можно вообще ничего не писать пользователю
            # либо максимум короткое подтверждение:
            # await message.answer("Сообщение передано в поддержку.")

            return

    except (TelegramBadRequest, TelegramAPIError):
        if message_thread_id:
            SupportTicketsRepo.close_by_thread_id(message_thread_id)
        await state.set_state(SupportState.send_request)
        await message.answer("Ваш тикет был закрыт или удалён. Напишите сообщение для нового обращения.")


@router.callback_query(F.data == "accept_privacy")
@private_only
async def accept_privacy(call: CallbackQuery, state: FSMContext):
    UsersRepo.accept_privacy(call.from_user.id, version="2026-02-05")
    await call.answer("Согласие принято ✅")
    await state.set_state(SupportState.send_request)
    await call.message.answer("Добро пожаловать в поддержку. Введите сообщение.")


@router.message()
@private_only
@require_privacy
async def fallback_no_state(message: types.Message, state: FSMContext):
    # Если состояние есть — пусть отрабатывают другие хендлеры
    if await state.get_state() is not None:
        return

    # 1) проверяем open тикет в БД
    ticket = SupportTicketsRepo.get_open_by_tg_id(message.from_user.id)
    if not ticket:
        await message.answer(
            "Ваш предыдущий запрос был закрыт.\n\n"
            "Чтобы открыть новое обращение, введите команду /start"
        )
        return

    thread_id = ticket["thread_id"]
    ticket_id = ticket["id"]

    # 2) пробуем отправить сообщение в существующий топик
    try:
        sent = await message.bot.forward_message(
            chat_id=SUPPORT_CHAT_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=thread_id,
        )

        # если улетело в general — считаем топик битым
        if not getattr(sent, "is_topic_message", False):
            try:
                await message.bot.delete_message(SUPPORT_CHAT_ID, sent.message_id)
            except Exception:
                pass

            # 3) восстанавливаем топик с тем же номером (#ticket_id)
            topic = await message.bot.create_forum_topic(
                chat_id=SUPPORT_CHAT_ID,
                name=f"{message.from_user.full_name or ''}".strip() or "Без имени",
            )
            new_thread_id = topic.message_thread_id
            try:
                await message.bot.edit_forum_topic(
                    chat_id=SUPPORT_CHAT_ID,
                    message_thread_id=new_thread_id,
                    name=f"{message.from_user.full_name or ''} | {message.from_user.username or message.from_user.id} #{ticket_id}",
                )
            except Exception:
                pass
            ok = SupportTicketsRepo.update_thread_id(ticket_id=ticket_id, new_thread_id=new_thread_id)
            if not ok:
                # тикет уже закрыт/удалён — просим пользователя открыть новый
                await state.set_state(SupportState.send_request)
                await message.answer("Тикет уже закрыт. Напишите сообщение для нового обращения.")
                return

            # 2.1) кнопка "Закрыть тикет" (aiogram 3 builder)
            kb = InlineKeyboardBuilder()
            kb.button(text="Закрыть тикет", callback_data="close_ticket")
            kb = kb.as_markup()

            # 2.2) пишем в топик и форвардим исходное сообщение
            uname = f"@{message.from_user.username}" if message.from_user.username else "без username"
            msg = await message.bot.send_message(
                chat_id=SUPPORT_CHAT_ID,
                message_thread_id=new_thread_id,
                text=f"Восстановлено обращение в тех. поддержку от пользователя {message.from_user.id} ({uname})",
                reply_markup=kb,
            )

            await message.bot.pin_chat_message(chat_id=SUPPORT_CHAT_ID,
                                       message_id=msg.message_id,
                                       disable_notification=True, )


            # 3) СРАЗУ повторно пересылаем сообщение в восстановленный топик
            await message.bot.forward_message(
                chat_id=SUPPORT_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=new_thread_id,
            )

            # 4) возвращаем пользователя в in_support
            await state.set_state(SupportState.in_support)

            # можно вообще ничего не писать пользователю
            # либо максимум короткое подтверждение:
            # await message.answer("Сообщение передано в поддержку.")

            return

        # 4) всё ок — подхватываем FSM и подтверждаем
        await state.set_state(SupportState.in_support)
        await message.answer("Сообщение отправлено в поддержку. Ожидайте ответа.")
        return

    except (TelegramBadRequest, TelegramAPIError):
        # если Telegram ругнулся — скорее всего топик/права сломаны
        # можно попробовать восстановление аналогично или попросить /start
        await message.answer(
            "Не удалось отправить сообщение в существующий тикет.\n"
            "Введите /start, чтобы открыть новое обращение."
        )
