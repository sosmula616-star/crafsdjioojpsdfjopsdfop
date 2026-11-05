import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN", "MTU2NjIwNDM0NjI2MDI2Mjk4Mg.G5BqB9.i_ZkNdwnOIUry2n1aApd8wKjW2HsZj_jpuB_Fk")
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "MTQzNDUzODU4NjA0MDE3NjgwMA.Gq4l2u.M_jaHdEiIrZvqDnYJb0acpDeGwS0CyZAMLB5lI")

STAFF_GUILD_ID = int(os.getenv("STAFF_GUILD_ID", "944591275091431424"))
MAIN_GUILD_ID = int(os.getenv("MAIN_GUILD_ID", "254958490676625408"))

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
TOKEN_EMOJI = os.getenv("TOKEN_EMOJI", "<:SupportToken:1425839493750984774>")

# Роли на сервере 254958490676625408:
# SUPPORT_ROLE_ID — роль саппорта (доступ к /support profile, /prime list; им считается время в прихожих)
# CURATOR_ROLE_IDS — роли кураторов (дают доступ к редактированию/админ-командам; норма в прихожих им не считается)
SUPPORT_ROLE_ID = 848876547792306217
CURATOR_ROLE_IDS = {848876541009592341, 1234034864228012095}
EXEMPT_ROLE_IDS = CURATOR_ROLE_IDS

LOBBY_CHANNELS = {
    1479082408543522917: "1 Прихожая",
    1500878409394426008: "2 Прихожая",
    1500878371762999457: "3 Прихожая",
    1500878462070685696: "4 Прихожая",
    1500878489899761684: "5 Прихожая",
    1500878516508688505: "6 Прихожая",
    1500878724147707994: "7 Прихожая",
    1500878776572182738: "8 Прихожая",
    1500878843903213609: "9 Прихожая",
    1500878888455110818: "10 Прихожая",
}

REPRIMAND_CHANNEL_ID = 853799479949524992
TICKETS_CHANNEL_ID = 1112301782098514016
MAX_WARNS = 3

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

BRIDGE_HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8080"))
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "super_secret_key_123")

MIN_PRIME_MINUTES = 47
TIMEZONE = "Europe/Moscow"

ALL_SLOTS = [f"{h}:00-{(h + 1) % 24}:00" for h in range(24)]
