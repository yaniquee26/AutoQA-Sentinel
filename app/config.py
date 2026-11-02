import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN. Создай файл .env по образцу .env.example")

ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
if ALLOWED_USER_ID == 0:
    raise RuntimeError("Не найден ALLOWED_USER_ID. Укажи свой Telegram ID в .env")

# Необязательно: локальная модель (Ollama) для кнопки «Объяснить»
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# Облачный режим: LLM_PROVIDER=openai (любой сервис с OpenAI-совместимым API, например Groq)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "")
if LLM_PROVIDER not in ("ollama", "openai"):
    raise RuntimeError("LLM_PROVIDER должен быть ollama или openai")
if LLM_PROVIDER == "openai" and not (LLM_BASE_URL and LLM_MODEL and LLM_API_KEY):
    raise RuntimeError("Для LLM_PROVIDER=openai укажи LLM_BASE_URL, LLM_MODEL и LLM_API_KEY в .env")
