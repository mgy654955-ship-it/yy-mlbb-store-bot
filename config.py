# config.py — MLBB Top-Up Bot (Manual Order)
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

PAYMENT_NAME = os.getenv("PAYMENT_NAME", "မင်းနာမည်")
PAYMENT_KBZ = os.getenv("PAYMENT_KBZ", "09XXXXXXXXX")
PAYMENT_WAVE = os.getenv("PAYMENT_WAVE", "09XXXXXXXXX")

PRODUCTS = {
    "dia_3": {"name": "💎 3 Diamond", "price": 500},
    "dia_86": {"name": "💎 86 Diamond", "price": 6500},
    "dia_172": {"name": "💎 172 Diamond", "price": 12500},
    "dia_257": {"name": "💎 257 Diamond", "price": 18500},
    "dia_706": {"name": "💎 706 Diamond", "price": 50000},
    "dia_1050": {"name": "💎 1050 Diamond", "price": 75000},
    "wp_1": {"name": "🎫 Weekly Pass x1", "price": 7000},
    "wp_2": {"name": "🎫 Weekly Pass x2", "price": 14000},
    "wp_3": {"name": "🎫 Weekly Pass x3", "price": 21000},
}

DIAMOND_KEYS = ["dia_3", "dia_86", "dia_172", "dia_257", "dia_706", "dia_1050"]
WEEKLY_KEYS = ["wp_1", "wp_2", "wp_3"]

DB_PATH = os.path.join(os.path.dirname(__file__), "orders.db")
