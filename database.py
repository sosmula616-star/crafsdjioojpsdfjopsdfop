import aiosqlite
from datetime import datetime
import pytz
from config import TIMEZONE, MAX_WARNS

DB_PATH = "support_bot.db"

def now_str() -> str:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%d.%m.%Y")

def current_slot_str() -> str:
    tz = pytz.timezone(TIMEZONE)
    h = datetime.now(tz).hour
    return f"{h}:00-{(h + 1) % 24}:00"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS log_threads (
                category TEXT PRIMARY KEY,
                thread_id INTEGER NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS supports (
                user_id INTEGER PRIMARY KEY,
                hire_date TEXT NOT NULL,
                prime_time TEXT DEFAULT NULL,
                balance INTEGER DEFAULT 0,
                probation_until TEXT DEFAULT NULL,
                vacation_until TEXT DEFAULT NULL,
                first_pt_shield INTEGER DEFAULT 1,
                weekly_misses INTEGER DEFAULT 0,
                admitted INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                total_minutes INTEGER DEFAULT 0,
                swaps_taken INTEGER DEFAULT 0,
                tickets INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0,
                is_exempt INTEGER DEFAULT 0
            )
        ''')
        try:
            await db.execute("ALTER TABLE supports ADD COLUMN is_exempt INTEGER DEFAULT 0")
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS processed_events (
                event_key TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_activity (
                user_id INTEGER,
                date_str TEXT,
                slot TEXT,
                minutes INTEGER DEFAULT 0,
                is_extra INTEGER DEFAULT 0,
                replaced_by INTEGER DEFAULT NULL,
                PRIMARY KEY (user_id, date_str, slot)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS swap_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_id INTEGER NOT NULL,
                date_str TEXT NOT NULL,
                slot TEXT NOT NULL,
                taken_by INTEGER DEFAULT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                bought_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward INTEGER NOT NULL,
                uses_left INTEGER NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS promo_used (
                user_id INTEGER,
                code TEXT,
                PRIMARY KEY (user_id, code)
            )
        ''')
        async with db.execute("SELECT COUNT(*) FROM shop_items") as cur:
            cnt = (await cur.fetchone())[0]
            if cnt == 0:
                await db.executemany(
                    "INSERT INTO shop_items (name, price) VALUES (?, ?)",
                    [("Снятие выговора", 500), ("Иммунитет на ПТ", 300), ("Кастомная роль", 1000)]
                )
        await db.commit()

async def mark_event_processed(event_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM processed_events WHERE event_key = ?", (event_key,)) as cur:
            if await cur.fetchone():
                return False
        await db.execute(
            "INSERT INTO processed_events (event_key, created_at) VALUES (?, ?)",
            (event_key, now_str())
        )
        await db.commit()
        return True

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value))
        )
        await db.commit()

async def get_setting(key: str, default: str = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def save_thread_id(category: str, thread_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO log_threads (category, thread_id) VALUES (?, ?) ON CONFLICT(category) DO UPDATE SET thread_id = excluded.thread_id",
            (category, thread_id)
        )
        await db.commit()

async def get_saved_thread_id(category: str) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT thread_id FROM log_threads WHERE category = ?", (category,)) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else None

async def ensure_support(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM supports WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
        hire = now_str()
        await db.execute(
            "INSERT INTO supports (user_id, hire_date, first_pt_shield) VALUES (?, ?, 1)",
            (user_id, hire)
        )
        await db.commit()
        async with db.execute("SELECT * FROM supports WHERE user_id = ?", (user_id,)) as cur:
            return dict(await cur.fetchone())

async def get_support(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM supports WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_all_supports() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM supports") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def update_support_field(user_id: int, field: str, value):
    await ensure_support(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE supports SET {field} = ? WHERE user_id = ?", (value, user_id))
        await db.commit()

async def change_warns(user_id: int, delta: int = 1, exact: int | None = None) -> int:
    data = await ensure_support(user_id)
    if exact is not None:
        new_warns = max(0, min(MAX_WARNS, exact))
    else:
        new_warns = max(0, min(MAX_WARNS, data.get("warns", 0) + delta))
    await update_support_field(user_id, "warns", new_warns)
    return new_warns

async def increment_stat(user_id: int, field: str, delta: int = 1) -> int:
    await ensure_support(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE supports SET {field} = MAX(0, {field} + ?) WHERE user_id = ?", (delta, user_id))
        await db.commit()
    data = await ensure_support(user_id)
    return data.get(field, 0)

async def delete_support(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM supports WHERE user_id = ?", (user_id,))
        await db.commit()

async def add_activity_minutes(user_id: int, date_str: str, slot: str, minutes: int, is_extra: int = 0):
    await ensure_support(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO daily_activity (user_id, date_str, slot, minutes, is_extra)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_str, slot)
            DO UPDATE SET minutes = minutes + excluded.minutes
        ''', (user_id, date_str, slot, minutes, is_extra))
        await db.execute(
            "UPDATE supports SET total_minutes = total_minutes + ? WHERE user_id = ?",
            (minutes, user_id)
        )
        await db.commit()

async def set_activity_minutes(user_id: int, date_str: str, slot: str, minutes: int, is_extra: int = 0):
    await ensure_support(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO daily_activity (user_id, date_str, slot, minutes, is_extra)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_str, slot)
            DO UPDATE SET minutes = excluded.minutes
        ''', (user_id, date_str, slot, minutes, is_extra))
        await db.commit()
