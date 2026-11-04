import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN", "MTU2NjIwNDM0NjI2MDI2Mjk4Mg.G5BqB9.i_ZkNdwnOIUry2n1aApd8wKjW2HsZj_jpuB_Fk")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
TOKEN_EMOJI = os.getenv("TOKEN_EMOJI", "<:SupportToken:1425839493750984774>")

# Названия веток, которые бот автоматически создаёт в канале логов
THREAD_NAMES = {
    "news": "Новости",
    "warns": "Выговоры",
    "removals": "Снятия",
    "reports": "Отчёты",
    "shop": "Магазин",
    "meetings": "Собрания",
    "tokens": "Токены",
    "primes": "Прайм-таймы",
    "swaps": "Замены",
}

BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8080"))
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "super_secret_key_123")

MIN_PRIME_MINUTES = 47
TIMEZONE = "Europe/Moscow"

ALL_SLOTS = [f"{h}:00-{(h + 1) % 24}:00" for h in range(24)]
