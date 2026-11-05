import re
import discord
from discord.ext import commands
from config import TICKETS_CHANNEL_ID, STAFF_GUILD_ID, MAIN_GUILD_ID
from database import increment_stat, mark_event_processed

class TicketsListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _collect_embed_text(self, embed: discord.Embed) -> str:
        parts = []
        if embed.title:
            parts.append(embed.title)
        if embed.author and embed.author.name:
            parts.append(embed.author.name)
        if embed.description:
            parts.append(embed.description)
        for f in embed.fields:
            parts.append(f"{f.name}:\n{f.value}")
        return "\n".join(parts)

    async def _resolve_support_id(self, raw_section: str) -> int | None:
        m = re.search(r"<@!?(\d{15,21})>", raw_section)
        if m:
            return int(m.group(1))

        names_to_try = []
        at_match = re.search(r"@([^\s|]+)", raw_section)
        if at_match:
            names_to_try.append(at_match.group(1).strip())
        pipe_match = re.search(r"\|\s*([^\s#\n]+)", raw_section)
        if pipe_match:
            names_to_try.append(pipe_match.group(1).strip())

        for candidate in names_to_try:
            cand_low = candidate.lower()
            for g_id in (STAFF_GUILD_ID, MAIN_GUILD_ID):
                guild = self.bot.get_guild(g_id)
                if not guild:
                    continue
                for member in guild.members:
                    if cand_low in (
                        member.name.lower(),
                        member.display_name.lower(),
                        (member.global_name or "").lower()
                    ):
                        return member.id
        return None

    async def _process_ticket_message(self, message: discord.Message):
        if message.channel.id != TICKETS_CHANNEL_ID:
            return
        if not message.embeds:
            return

        for embed in message.embeds:
            full_text = self._collect_embed_text(embed)
            if "Тикет был закрыт" not in full_text:
                continue

            ticket_id_match = re.search(r"ID тикета[:\s]*\n?\s*(\d+)", full_text, re.IGNORECASE)
            ticket_key = f"ticket_{ticket_id_match.group(1)}" if ticket_id_match else f"ticket_msg_{message.id}"

            accepted_section = ""
            for f in embed.fields:
                if "Тикет принял" in f.name:
                    accepted_section = f.value
                    break
            if not accepted_section:
                m_sec = re.search(r"Тикет принял[:\s]*\n?(.+)", full_text, re.IGNORECASE)
                if m_sec:
                    accepted_section = m_sec.group(1)

            if not accepted_section:
                continue

            support_id = await self._resolve_support_id(accepted_section)
            if not support_id:
                continue

            if not await mark_event_processed(ticket_key):
                return

            new_tickets = await increment_stat(support_id, "tickets", 1)
            print(f"[Tickets] Засчитан закрытый тикет ({ticket_key}) саппорту {support_id} (Всего: {new_tickets})")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self._process_ticket_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await self._process_ticket_message(after)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsListenerCog(bot))
