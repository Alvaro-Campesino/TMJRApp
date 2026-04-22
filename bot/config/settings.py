import logging
from dotenv import load_dotenv
import os, ast

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEBUG = ast.literal_eval(os.getenv("DEBUG"))
API_BASE_URL = os.getenv("API_BASE_URL")

logger = logging.getLogger("logger")
logging_level = logging.INFO if DEBUG else logging.WARNING
# Esto evita los constantes avisos de la api de Telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(filename="logs/tgbot.log", level=logging_level)
