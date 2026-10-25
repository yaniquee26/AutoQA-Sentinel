from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import ALLOWED_USER_ID
from app.runner import format_report, run_checks
from app.storage import get_flaky, get_recent_runs, save_run

router = Router()


def is_allowed(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id == ALLOWED_USER_ID


def format_run_line(run: dict) -> str:
    ok = run["failed"] == 0 and run["errors"] == 0
    icon = "✅" if ok else "❌"
    target = run["target"].split("/")[-1]
    return f'#{run["id"]} {target} {run["created_at"]} {icon} {run["passed"]}/{run["total"]}, {run["duration"]:.1f} с'


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
        "/flaky - нестабильные проверки"
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("pong")


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой Telegram ID: {message.from_user.id}")


async def run_target(message: Message, target: str, title: str):
    if not is_allowed(message):
        await message.answer("Нет доступа.")
        return
    await message.answer(f"Запускаю {title}, это займёт некоторое время...")
    result = await run_checks(target)
    if not result.crashed and result.total > 0:
        save_run(target, result)
    await message.answer(format_report(result))


@router.message(Command("run_api"))
async def cmd_run_api(message: Message):
    await run_target(message, "checks/api", "API-проверки")


@router.message(Command("run_ui"))
async def cmd_run_ui(message: Message):
    await run_target(message, "checks/ui", "UI-проверки")


@router.message(Command("last"))
async def cmd_last(message: Message):
    if not is_allowed(message):
        await message.answer("Нет доступа.")
        return
    runs = get_recent_runs(1)
    if not runs:
        await message.answer("Прогонов пока нет. Запусти /run_api")
        return
    await message.answer(format_run_line(runs[0]))


@router.message(Command("history"))
async def cmd_history(message: Message):
    if not is_allowed(message):
        await message.answer("Нет доступа.")
        return
    runs = get_recent_runs(5)
    if not runs:
        await message.answer("Прогонов пока нет. Запусти /run_api")
        return
    await message.answer("\n".join(format_run_line(run) for run in runs))


@router.message(Command("flaky"))
async def cmd_flaky(message: Message):
    if not is_allowed(message):
        await message.answer("Нет доступа.")
        return
    items = get_flaky(10)
    if not items:
        await message.answer("Нестабильных проверок не найдено (последние 10 прогонов).")
        return
    lines = ["Нестабильные проверки (последние 10 прогонов):"]
    for item in items:
        lines.append(f'- {item["test_name"]}: прошла {item["passed"]}, упала {item["failed"]}')
    await message.answer("\n".join(lines))