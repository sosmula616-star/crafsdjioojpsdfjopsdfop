from aiohttp import web
from discord.ext import commands
import aiosqlite
from config import BRIDGE_HOST, BRIDGE_PORT, BRIDGE_SECRET, MAX_WARNS
from database import (
    add_activity_minutes,
    ensure_support,
    update_support_field,
    change_warns,
    now_str,
    DB_PATH
)
from utils.logger import send_log

class BridgeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner = None

    async def cog_load(self):
        app = web.Application()
        app.router.add_post("/api/activity", self.handle_activity)
        app.router.add_post("/api/stats", self.handle_stats)
        app.router.add_post("/api/reprimand", self.handle_reprimand)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        try:
            site = web.TCPSite(self.runner, BRIDGE_HOST, BRIDGE_PORT)
            await site.start()
        except Exception as e:
            print(f"[Bridge] Порт {BRIDGE_PORT} уже занят: {e}")

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()

    async def handle_activity(self, request: web.Request):
        if request.headers.get("X-Bridge-Secret") != BRIDGE_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)

        payload = await request.json()
        user_id = int(payload["user_id"])
        slot = payload["slot"]
        minutes = int(payload.get("minutes", 1))
        date_str = payload.get("date", now_str())
        is_exempt = int(payload.get("is_exempt", 0))

        await ensure_support(user_id)
        await update_support_field(user_id, "is_exempt", is_exempt)
        if not is_exempt:
            await add_activity_minutes(user_id, date_str, slot, minutes)
        return web.json_response({"status": "ok"})

    async def handle_stats(self, request: web.Request):
        if request.headers.get("X-Bridge-Secret") != BRIDGE_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)

        payload = await request.json()
        user_id = int(payload["user_id"])
        field = payload.get("field")
        delta = int(payload.get("delta", 1))

        if field not in ("admitted", "rejected", "tickets"):
            return web.json_response({"error": "invalid field"}, status=400)

        await ensure_support(user_id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE supports SET {field} = {field} + ? WHERE user_id = ?", (delta, user_id))
            await db.commit()

        return web.json_response({"status": "ok"})

    async def handle_reprimand(self, request: web.Request):
        if request.headers.get("X-Bridge-Secret") != BRIDGE_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)

        payload = await request.json()
        user_id = int(payload["user_id"])
        action = payload.get("action", "add")
        exact = payload.get("exact")
        reason = payload.get("reason", "Не указана")

        if exact is not None:
            new_w = await change_warns(user_id, exact=int(exact))
        else:
            delta = 1 if action == "add" else -1
            new_w = await change_warns(user_id, delta=delta)

        if action == "add":
            await send_log(
                self.bot,
                "warns",
                f"⚠️ Саппорт <@{user_id}> получил выговор (Причина: `{reason}`). Текущие выговоры: **`{new_w}/{MAX_WARNS}`**."
            )
        else:
            await send_log(
                self.bot,
                "warns",
                f"✅ У саппорта <@{user_id}> снят выговор. Текущие выговоры: **`{new_w}/{MAX_WARNS}`**."
            )

        return web.json_response({"status": "ok", "warns": new_w})


async def setup(bot: commands.Bot):
    await bot.add_cog(BridgeCog(bot))
