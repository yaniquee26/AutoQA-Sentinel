import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import BOT_TOKEN
from app.handlers import router
from app.storage import init_db


async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Удаляем вебхук, если он был включён раньше, и сбрасываем накопленные сообщения
    await bot.delete_webhook(drop_pending_updates=True)

    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())