from aiohttp import web
from discord.ext import commands
import aiosqlite
from config import BRIDGE_HOST, BRIDGE_PORT, BRIDGE_SECRET
from database import add_activity_minutes, ensure_support, now_str, DB_PATH

class BridgeCog(commands.Cog):
    '''
    HTTP-мост для связки со вторым ботом (который стоит на сервере с голосовыми каналами / прихожими).
    Второй бот может отправлять POST-запросы на http://IP:8080/api/activity
    с заголовком X-Bridge-Secret.
    '''
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.runner = None

    async def cog_load(self):
        app = web.Application()
        app.router.add_post("/api/activity", self.handle_activity)
        app.router.add_post("/api/stats", self.handle_stats)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, BRIDGE_HOST, BRIDGE_PORT)
        await site.start()

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

        await add_activity_minutes(user_id, date_str, slot, minutes)
        return web.json_response({"status": "ok"})

    async def handle_stats(self, request: web.Request):
        if request.headers.get("X-Bridge-Secret") != BRIDGE_SECRET:
            return web.json_response({"error": "unauthorized"}, status=401)

        payload = await request.json()
        user_id = int(payload["user_id"])
        field = payload.get("field")  # admitted, rejected, tickets
        delta = int(payload.get("delta", 1))

        if field not in ("admitted", "rejected", "tickets"):
            return web.json_response({"error": "invalid field"}, status=400)

        await ensure_support(user_id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE supports SET {field} = {field} + ? WHERE user_id = ?", (delta, user_id))
            await db.commit()

        return web.json_response({"status": "ok"})


async def setup(bot: commands.Bot):
    await bot.add_cog(BridgeCog(bot))
