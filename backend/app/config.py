import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Database
DB_PATH = DATA_DIR / "price_monitor.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Server Settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Decision Engine Thresholds
DISCOUNT_EXCELLENT_PCT = 7.0  # >= 7% below moving average is considered excellent
WITHIN_ALL_TIME_MIN_PCT = 3.0  # within 3% of all-time low is considered excellent
HIGH_PRICE_PCT = 5.0  # >= 5% above moving average is considered high
