import asyncio
import re
import discord
from discord.ext import commands, tasks
from config import (
    MONITOR_TOKEN,
    MAIN_GUILD_ID,
    SUPPORT_ROLE_ID,
    EXEMPT_ROLE_IDS,
    LOBBY_CHANNELS,
    REPRIMAND_CHANNEL_ID,
    MAX_WARNS
)
from database import (
    init_db,
    ensure_support,
    update_support_field,
    add_activity_minutes,
    change_warns,
    mark_event_processed,
    now_str,
    current_slot_str
)
from utils.logger import send_log

MONITOR_INTENTS = discord.Intents.default()
MONITOR_INTENTS.guilds = True
MONITOR_INTENTS.members = True
MONITOR_INTENTS.voice_states = True
MONITOR_INTENTS.messages = True
MONITOR_INTENTS.message_content = True


class MonitorBot(commands.Bot):
    def __init__(self, main_bot: commands.Bot | None = None):
        super().__init__(command_prefix="!mon_", intents=MONITOR_INTENTS)
        self.main_bot = main_bot

    async def setup_hook(self):
        await init_db()
        self.voice_activity_loop.start()

    async def on_ready(self):
        print(f"[+] Монитор-бот запущен как {self.user} (ID: {self.user.id})")
        guild = self.get_guild(MAIN_GUILD_ID)
        if guild:
            print(f"[+] Монитор-бот отслеживает сервер: {guild.name} ({guild.id})")

    @tasks.loop(seconds=60)
    async def voice_activity_loop(self):
        guild = self.get_guild(MAIN_GUILD_ID)
        if not guild:
            return

        date_str = now_str()
        slot_str = current_slot_str()

        for channel_id in LOBBY_CHANNELS:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                continue

            for member in channel.members:
                if member.bot:
                    continue

                role_ids = {r.id for r in member.roles}
                has_support = SUPPORT_ROLE_ID in role_ids
                has_exempt = bool(role_ids.intersection(EXEMPT_ROLE_IDS))

                if not has_support:
                    continue

                if has_exempt:
                    await ensure_support(member.id)
                    await update_support_field(member.id, "is_exempt", 1)
                    continue

                await ensure_support(member.id)
                await update_support_field(member.id, "is_exempt", 0)
                await add_activity_minutes(member.id, date_str, slot_str, 1)

    @voice_activity_loop.before_loop
    async def before_voice_loop(self):
        await self.wait_until_ready()

    def _extract_embed_text(self, embed: discord.Embed) -> str:
        parts = []
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        for f in embed.fields:
            parts.append(f"{f.name}\n{f.value}")
        return "\n".join(parts)

    async def _resolve_target_user_from_reprimand(self, text: str, guild: discord.Guild | None) -> int | None:
        mentions = re.findall(r"<@!?(\d{15,21})>", text)
        if len(mentions) >= 2:
            return int(mentions[1])

        m_id = re.search(r"пользователю\s*<@!?(\d{15,21})>", text, re.IGNORECASE)
        if m_id:
            return int(m_id.group(1))

        m_name = re.search(r"пользователю\s*@?([^.\n\r]+)", text, re.IGNORECASE)
        if m_name and guild:
            target_name = m_name.group(1).strip().lstrip("@").lower()
            for member in guild.members:
                if target_name in (
                    member.name.lower(),
                    member.display_name.lower(),
                    (member.global_name or "").lower()
                ):
                    return member.id
        return None

    async def _process_reprimand_message(self, message: discord.Message):
        if message.channel.id != REPRIMAND_CHANNEL_ID:
            return
        if not message.embeds:
            return

        for embed in message.embeds:
            full_text = self._extract_embed_text(embed)
            low_text = full_text.lower()

            is_issue = ("выдать выговор" in low_text) or ("выдали выговор" in low_text)
            is_remove = ("снять выговор" in low_text) or ("сняли выговор" in low_text)

            if not is_issue and not is_remove:
                continue

            target_id = await self._resolve_target_user_from_reprimand(full_text, message.guild)
            if not target_id:
                continue

            event_key = f"reprimand_{message.id}_{'add' if is_issue else 'rem'}_{target_id}"
            if not await mark_event_processed(event_key):
                return

            if is_issue:
                exact_match = re.search(r"Теперь у него\s*(\d+)\s*выговор", full_text, re.IGNORECASE)
                exact_val = int(exact_match.group(1)) if exact_match else None
                new_warns = await change_warns(target_id, delta=1, exact=exact_val)

                reason = "Не указана"
                for f in embed.fields:
                    if "причина" in f.name.lower():
                        reason = f.value.strip()
                        break

                print(f"[Warns] Выдан выговор саппорту {target_id}. Теперь: {new_warns}/{MAX_WARNS}")
                if self.main_bot:
                    await send_log(
                        self.main_bot,
                        "warns",
                        f"⚠️ Авто-фиксация: Саппорт <@{target_id}> получил выговор (Причина: `{reason}`). Теперь у него **`{new_warns}/{MAX_WARNS}`** выговоров."
                    )
            elif is_remove:
                new_warns = await change_warns(target_id, delta=-1)
                print(f"[Warns] Снят выговор у саппорта {target_id}. Теперь: {new_warns}/{MAX_WARNS}")
                if self.main_bot:
                    await send_log(
                        self.main_bot,
                        "warns",
                        f"✅ Авто-фиксация: У саппорта <@{target_id}> снят выговор. Теперь у него **`{new_warns}/{MAX_WARNS}`** выговоров."
                    )

    async def on_message(self, message: discord.Message):
        await self._process_reprimand_message(message)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await self._process_reprimand_message(after)


async def run_standalone():
    mon = MonitorBot()
    async with mon:
        await mon.start(MONITOR_TOKEN)

if __name__ == "__main__":
    asyncio.run(run_standalone())
