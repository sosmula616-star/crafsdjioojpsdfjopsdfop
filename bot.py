import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from config import BOT_TOKEN
from database import init_db
from utils.logger import get_bound_log_channel, ensure_all_log_threads

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.emojis_and_stickers = True
INTENTS.message_content = True

EXTENSIONS = (
    "cogs.admin_panel",
    "cogs.reports",
    "cogs.support_profile",
    "cogs.bridge",
)

class MitaSupportBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)
        self._synced_once = False

    async def setup_hook(self):
        await init_db()
        for ext in EXTENSIONS:
            await self.load_extension(ext)

    async def clean_and_sync_commands(self):
        # 1. Перезаписываем команды на каждом сервере (удаляет старые серверные команды)
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[+] Команды очищены и обновлены на сервере: {guild.name} ({guild.id})")

        # 2. Очищаем старые глобальные команды, чтобы не было дубликатов
        self.tree.clear_commands(guild=None)
        await self.tree.sync(guild=None)
        print("[+] Старые глобальные команды успешно удалены!")

    async def on_ready(self):
        print(f"[+] Бот запущен как {self.user} (ID: {self.user.id})")
        if not self._synced_once:
            self._synced_once = True
            await self.clean_and_sync_commands()

        channel = await get_bound_log_channel(self)
        if channel:
            threads = await ensure_all_log_threads(self, channel)
            print(f"[+] Ветки логов синхронизированы в #{channel.name} ({len(threads)} шт.)")


bot = MitaSupportBot()

@bot.tree.command(name="help", description="Список всех команд бота")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Команды бота MitaCloud",
        color=0x2B2D31,
        description=(
            "**👤 Для саппортов:**\n"
            "`/support profile` — Открыть свой профиль саппорта\n"
            "`/prime list` — Таблица всех прайм-таймов\n\n"
            "**🛠️ Админ-панель и настройка:**\n"
            "`/admin panel @саппорт` — Панель управления саппортом\n"
            "`/set_logs #канал` — Привязать канал логов (сам создаст 9 веток)\n\n"
            "**🪙 Работа с токенами:**\n"
            "`/award @саппорт [кол-во] [причина]` — Выдать токены\n"
            "`/take @саппорт [кол-во] [причина]` — Забрать токены\n\n"
            "**🕒 Работа с прайм-таймами:**\n"
            "`/prime set @саппорт [слот]` — Назначить/сменить ПТ (напр. 20:00-21:00)\n"
            "`/prime remove @саппорт` — Удалить ПТ у саппорта\n\n"
            "**📊 Работа с отчётами (для Лизы):**\n"
            "`/prime add @саппорт [дата]` — Засчитать ПТ (по умолчанию за сегодня)\n"
            "`/miss @саппорт [кол-во]` — Вычесть прогул из отчётов\n\n"
            "**✉️ Другое:**\n"
            "`/swap_as @саппорт [дата]` — Запросить замену от имени саппорта\n"
            "`/dm @пользователь [текст]` — Написать в ЛС от имени бота"
        )
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def main():
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
