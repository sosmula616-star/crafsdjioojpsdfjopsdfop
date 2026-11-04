import asyncio
import discord
from discord.ext import commands
from config import BOT_TOKEN, GUILD_ID
from database import init_db
from utils.logger import get_bound_log_channel, ensure_all_log_threads

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.emojis_and_stickers = True
INTENTS.message_content = True

class MitaSupportBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        await init_db()
        for ext in ("cogs.admin_panel", "cogs.reports", "cogs.support_profile", "cogs.bridge"):
            await self.load_extension(ext)

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        print(f"[+] Бот запущен как {self.user} (ID: {self.user.id})")
        # Если канал логов уже указан в .env или БД — автоматически проверяем и создаём все 9 веток
        channel = await get_bound_log_channel(self)
        if channel:
            threads = await ensure_all_log_threads(self, channel)
            print(f"[+] Ветки логов синхронизированы в #{channel.name} ({len(threads)} шт.)")


async def main():
    bot = MitaSupportBot()
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
