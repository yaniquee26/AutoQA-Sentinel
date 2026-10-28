import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.config import ALLOWED_USER_ID
from app.runner import format_report, run_checks
from app.storage import get_flaky, get_recent_runs, save_run

router = Router()
RUN_LOCK = asyncio.Lock()


def is_allowed(user_id: int) -> bool:
    return user_id == ALLOWED_USER_ID


def user_id_of(message: Message) -> int:
    return message.from_user.id if message.from_user else 0


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶ API", callback_data="run_api"),
                InlineKeyboardButton(text="▶ UI", callback_data="run_ui"),
            ],
            [
                InlineKeyboardButton(text="📜 История", callback_data="history"),
                InlineKeyboardButton(text="🔥 Нестабильные", callback_data="flaky"),
            ],
        ]
    )


def format_run_line(run: dict) -> str:
    ok = run["failed"] == 0 and run["errors"] == 0
    icon = "✅" if ok else "❌"
    target = run["target"].split("/")[-1]
    return f'#{run["id"]} {target} {run["created_at"]} {icon} {run["passed"]}/{run["total"]}, {run["duration"]:.1f} с'


def history_text() -> str:
    runs = get_recent_runs(5)
    if not runs:
        return "Прогонов пока нет. Запусти /run_api"
    return "\n".join(format_run_line(run) for run in runs)


def flaky_text() -> str:
    items = get_flaky(10)
    if not items:
        return "Нестабильных проверок не найдено (последние 10 прогонов)."
    lines = ["Нестабильные проверки (последние 10 прогонов):"]
    for item in items:
        lines.append(f'- {item["test_name"]}: прошла {item["passed"]}, упала {item["failed"]}')
    return "\n".join(lines)


async def run_target(message: Message, user_id: int, target: str, title: str):
    if not is_allowed(user_id):
        await message.answer("Нет доступа.")
        return
    if RUN_LOCK.locked():
        await message.answer("Уже идёт другой прогон, подожди его окончания.")
        return
    async with RUN_LOCK:
        await message.answer(f"Запускаю {title}, это займёт некоторое время...")
        result = await run_checks(target)
        if not result.crashed and result.total > 0:
            save_run(target, result)
    for path in result.screenshots:
        await message.answer_photo(FSInputFile(path), caption=path.parent.name[:200])
    await message.answer(format_report(result), reply_markup=main_keyboard())


async def run_from_callback(callback: CallbackQuery, target: str, title: str):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    if callback.message is not None:
        await run_target(callback.message, callback.from_user.id, target, title)


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я AutoQA Sentinel.\n"
        "Команды:\n"
        "/ping - проверка связи\n"
        "/id - узнать свой Telegram ID\n"
        "/run_api - запустить API-проверки\n"
        "/run_ui - запустить UI-проверки\n"
        "/last - последний прогон\n"
        "/history - последние 5 прогонов\n"
        "/flaky - нестабильные проверки\n\n"
        "Или нажми кнопку:",
        reply_markup=main_keyboard(),
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong")


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой Telegram ID: {user_id_of(message)}")


@router.message(Command("run_api"))
async def cmd_run_api(message: Message):
    await run_target(message, user_id_of(message), "checks/api", "API-проверки")


@router.message(Command("run_ui"))
async def cmd_run_ui(message: Message):
    await run_target(message, user_id_of(message), "checks/ui", "UI-проверки")


@router.message(Command("last"))
async def cmd_last(message: Message):
    if not is_allowed(user_id_of(message)):
        await message.answer("Нет доступа.")
        return
    runs = get_recent_runs(1)
    if not runs:
        await message.answer("Прогонов пока нет. Запусти /run_api")
        return
    await message.answer(format_run_line(runs[0]), reply_markup=main_keyboard())


@router.message(Command("history"))
async def cmd_history(message: Message):
    if not is_allowed(user_id_of(message)):
        await message.answer("Нет доступа.")
        return
    await message.answer(history_text(), reply_markup=main_keyboard())


@router.message(Command("flaky"))
async def cmd_flaky(message: Message):
    if not is_allowed(user_id_of(message)):
        await message.answer("Нет доступа.")
        return
    await message.answer(flaky_text(), reply_markup=main_keyboard())


@router.callback_query(F.data == "run_api")
async def cb_run_api(callback: CallbackQuery):
    await run_from_callback(callback, "checks/api", "API-проверки")


@router.callback_query(F.data == "run_ui")
async def cb_run_ui(callback: CallbackQuery):
    await run_from_callback(callback, "checks/ui", "UI-проверки")


@router.callback_query(F.data == "history")
async def cb_history(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(history_text(), reply_markup=main_keyboard())


@router.callback_query(F.data == "flaky")
async def cb_flaky(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(flaky_text(), reply_markup=main_keyboard())