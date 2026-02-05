import config
import logging

from db_logic.database import Base, engine

from routers.support.user_handlers import router as user_router
from routers.support.admin_handlers import router as admin_router

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app import storage


# Для создания моделей не удалять
import db_logic.models


# Создаем таблицу в базе данных, если она не существует
def init_db():
    Base.metadata.create_all(bind=engine)


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,  # потом можно вынести в config.LOG_LEVEL
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main():
    setup_logging()
    init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    dp.include_router(admin_router)
    dp.include_router(user_router)


    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
