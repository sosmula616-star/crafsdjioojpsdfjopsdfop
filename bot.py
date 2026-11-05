import asyncio
import discord
from discord.ext import commands
from config import BOT_TOKEN, MONITOR_TOKEN
from database import init_db
from utils.logger import get_bound_log_channel, ensure_all_log_threads
from utils.permissions import set_monitor_bot_instance, can_use_support_commands
from monitor_bot import MonitorBot

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.emojis_and_stickers = True
INTENTS.message_content = True

EXTENSIONS = (
    "cogs.admin_panel",
    "cogs.reports",
    "cogs.support_profile",
    "cogs.tickets_listener",
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

    async def force_wipe_and_sync(self):
        app_id = self.application_id
        try:
            global_cmds = await self.http.get_global_commands(app_id)
            for cmd in global_cmds:
                try:
                    await self.http.delete_global_command(app_id, cmd["id"])
                    print(f"[-] Удалена старая глобальная команда: /{cmd.get('name')}")
                except Exception as e:
                    print(f"[!] Не удалось удалить /{cmd.get('name')}: {e}")
        except Exception as e:
            print(f"[!] Ошибка чтения глобальных команд: {e}")

        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"[+] Команды синхронизированы для сервера: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"[!] Ошибка синхронизации на сервере {guild.name}: {e}")

    async def on_ready(self):
        print(f"[+] Основной бот запущен как {self.user} (ID: {self.user.id})")
        if not self._synced_once:
            self._synced_once = True
            await self.force_wipe_and_sync()

        channel = await get_bound_log_channel(self)
        if channel:
            threads = await ensure_all_log_threads(self, channel)
            print(f"[+] Ветки логов синхронизированы в #{channel.name} ({len(threads)} шт.)")


bot = MitaSupportBot()

@bot.tree.command(name="help", description="Список всех команд бота")
async def help_cmd(interaction: discord.Interaction):
    if not await can_use_support_commands(interaction):
        return
    embed = discord.Embed(
        title="📖 Команды бота",
        color=0x2B2D31,
        description=(
            "**👤 Для саппортов:**\n"
            "`/support profile [пользователь/ID]` — Открыть свой или чужой профиль саппорта\n"
            "`/prime list` — Таблица всех прайм-таймов\n\n"
            "**🛠️ Админ-панель и настройка:**\n"
            "`/admin panel [саппорт/ID]` — Панель управления саппортом (ПТ, выговоры, отпуск)\n"
            "`/set_logs #канал` — Привязать канал логов (сам создаст 9 веток)\n"
            "`/report now [дата]` — Сформировать отчёт активности по запросу\n\n"
            "**🪙 Работа с токенами:**\n"
            "`/award [саппорт/ID] [кол-во] [причина]` — Выдать токены\n"
            "`/take [саппорт/ID] [кол-во] [причина]` — Забрать токены\n\n"
            "**🕒 Работа с прайм-таймами:**\n"
            "`/prime set [саппорт/ID]` — Открыть интерактивную панель выбора ПТ\n"
            "`/prime remove [саппорт/ID]` — Удалить ПТ у саппорта\n\n"
            "**📊 Работа с отчётами:**\n"
            "`/prime add [саппорт/ID] [дата]` — Засчитать ПТ (по умолчанию за сегодня)\n"
            "`/miss [саппорт/ID] [кол-во]` — Вычесть прогул из отчётов\n\n"
            "**✉️ Другое:**\n"
            "`/swap_as [саппорт/ID] [дата]` — Запросить замену от имени саппорта\n"
            "`/dm @пользователь [текст]` — Написать в ЛС от имени бота"
        )
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def main():
    monitor = MonitorBot(main_bot=bot)
    set_monitor_bot_instance(monitor)

    async def start_main():
        try:
            await bot.start(BOT_TOKEN.strip())
        except discord.LoginFailure:
            print("❌ [ОШИБКА] Неверный токен ОСНОВНОГО бота (DISCORD_TOKEN)! Сбросьте его в Discord Developer Portal.")
            raise

    async def start_monitor():
        try:
            await monitor.start(MONITOR_TOKEN.strip())
        except discord.LoginFailure:
            print("❌ [ОШИБКА] Неверный токен ВТОРОГО бота-монитора (MONITOR_TOKEN)! Сбросьте его в Discord Developer Portal.")
            except_err = True

    await asyncio.gather(
        start_main(),
        start_monitor(),
    )

if __name__ == "__main__":
    asyncio.run(main())
