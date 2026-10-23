import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN. Создай файл .env по образцу .env.example")

ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))