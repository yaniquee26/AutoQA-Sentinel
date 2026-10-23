from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import ALLOWED_USER_ID
from app.runner import format_report, run_checks

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я AutoQA Sentinel.\n"
        "Команды:\n"
        "/ping - проверка связи\n"
        "/id - узнать свой Telegram ID\n"
        "/run_api - запустить API-проверки"
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong")


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой Telegram ID: {message.from_user.id}")


@router.message(Command("run_api"))
async def cmd_run_api(message: Message):
    if message.from_user.id != ALLOWED_USER_ID:
        await message.answer("Нет доступа.")
        return
    await message.answer("Запускаю API-проверки, это займёт несколько секунд...")
    result = await run_checks("checks/api")
    await message.answer(format_report(result))