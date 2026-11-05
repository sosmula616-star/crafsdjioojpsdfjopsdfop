import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import pytz
import aiosqlite
from config import TIMEZONE, ALL_SLOTS, MIN_PRIME_MINUTES
from database import DB_PATH, get_all_supports, update_support_field, now_str
from utils.logger import send_log
from utils.permissions import check_support_status

tz = pytz.timezone(TIMEZONE)
CODE_BLOCK = chr(96) * 3

class ExplainModal(discord.ui.Modal, title="Объяснительная по пропуску ПТ"):
    reason = discord.ui.TextInput(
        label="Почему вы не досидели прайм-тайм?",
        style=discord.TextStyle.paragraph,
        placeholder="Опишите причину...",
        required=True,
        max_length=1000
    )

    def __init__(self, slot: str, minutes: int, date_str: str):
        super().__init__()
        self.slot = slot
        self.minutes = minutes
        self.date_str = date_str

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📝 Новая объяснительная",
            color=0x5865F2,
            timestamp=datetime.now(tz)
        )
        embed.add_field(name="Саппорт", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        embed.add_field(name="Прайм-тайм", value=f"`{self.slot}` ({self.date_str})", inline=True)
        embed.add_field(name="Отсижено", value=f"`{self.minutes} из 60 мин.`", inline=True)
        embed.add_field(name="Причина", value=self.reason.value, inline=False)

        await send_log(interaction.client, "reports", embed=embed)
        await interaction.response.send_message("✅ Ваша объяснительная отправлена в ветку отчётов!", ephemeral=True)


class ExplainView(discord.ui.View):
    def __init__(self, slot: str, minutes: int, date_str: str):
        super().__init__(timeout=None)
        self.slot = slot
        self.minutes = minutes
        self.date_str = date_str

    @discord.ui.button(label="Объясниться", style=discord.ButtonStyle.primary)
    async def explain_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExplainModal(self.slot, self.minutes, self.date_str))


class ReportsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_notified_key = None
        self.midnight_report_task.start()
        self.pt_reminder_task.start()

    report_group = app_commands.Group(name="report", description="Управление ежедневными отчётами активности")

    def cog_unload(self):
        self.midnight_report_task.cancel()
        self.pt_reminder_task.cancel()

    @report_group.command(name="now", description="Сформировать и отправить отчёт активности по запросу")
    @app_commands.describe(
        дата="За какую дату ДД.ММ.ГГГГ (по умолчанию за сегодня)",
        в_ветку_логов="Также продублировать отчёт в ветку #Отчёты (по умолчанию Да)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def report_now_cmd(self, interaction: discord.Interaction, дата: str = None, в_ветку_логов: bool = True):
        await interaction.response.defer(ephemeral=False)
        target_date = дата.strip() if дата else now_str()
        rep_embed, truant_embed = await self.generate_and_send_report(
            target_date,
            is_monday=False,
            update_penalties=False,
            send_to_log_thread=в_ветку_логов
        )
        embeds = [rep_embed]
        if truant_embed:
            embeds.append(truant_embed)
        await interaction.followup.send(
            content=f"📊 **Отчёт по запросу за `{target_date}`:**",
            embeds=embeds
        )

    async def get_users_for_slot(self, slot: str, today_str: str) -> set[int]:
        supports = await get_all_supports()
        target_users: set[int] = set()

        for sup in supports:
            if sup.get("is_exempt"):
                continue
            if sup.get("prime_time") == slot:
                in_vacation = False
                if sup.get("vacation_until"):
                    try:
                        vac_dt = datetime.strptime(sup["vacation_until"], "%d.%m.%Y").date()
                        cur_dt = datetime.strptime(today_str, "%d.%m.%Y").date()
                        if cur_dt <= vac_dt:
                            in_vacation = True
                    except Exception:
                        pass
                if not in_vacation:
                    target_users.add(sup["user_id"])

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, is_extra, replaced_by FROM daily_activity WHERE date_str = ? AND slot = ?",
                (today_str, slot)
            ) as cur:
                for row in await cur.fetchall():
                    if row["is_extra"] == 1:
                        target_users.add(row["user_id"])
                    if row["replaced_by"]:
                        target_users.discard(row["user_id"])
                        target_users.add(row["replaced_by"])

        return target_users

    @tasks.loop(seconds=30)
    async def pt_reminder_task(self):
        now = datetime.now(tz)
        today_str = now.strftime("%d.%m.%Y")

        if now.minute == 55:
            next_hour = (now.hour + 1) % 24
            end_hour = (next_hour + 1) % 24
            slot = f"{next_hour}:00-{end_hour}:00"
            key = f"{today_str}_{slot}_5min"
            if self._last_notified_key == key:
                return
            self._last_notified_key = key

            user_ids = await self.get_users_for_slot(slot, today_str)
            embed = discord.Embed(
                title="⏰ Через 5 минут начнётся ваш прайм-тайм",
                description=(
                    "**Слот:**\n"
                    f"{CODE_BLOCK}\n{slot}\n{CODE_BLOCK}\n"
                    "> Не забудьте зайти в прихожую и отсидеть прайм-тайм!"
                ),
                color=0x2B2D31
            )
            for uid in user_ids:
                await self._send_dm_safe(uid, embed)

        elif now.minute == 0:
            cur_hour = now.hour
            end_hour = (cur_hour + 1) % 24
            slot = f"{cur_hour}:00-{end_hour}:00"
            key = f"{today_str}_{slot}_start"
            if self._last_notified_key == key:
                return
            self._last_notified_key = key

            user_ids = await self.get_users_for_slot(slot, today_str)
            embed = discord.Embed(
                title="🚀 Ваш прайм-тайм начался!",
                description=(
                    "**Слот:**\n"
                    f"{CODE_BLOCK}\n{slot}\n{CODE_BLOCK}\n"
                    "> Желаю удачных верификаций!"
                ),
                color=0x2B2D31
            )
            for uid in user_ids:
                await self._send_dm_safe(uid, embed)

    @pt_reminder_task.before_loop
    async def before_pt_reminder(self):
        await self.bot.wait_until_ready()

    async def _send_dm_safe(self, user_id: int, embed: discord.Embed):
        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception:
                return
        try:
            await user.send(embed=embed)
        except Exception:
            pass

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=tz))
    async def midnight_report_task(self):
        now = datetime.now(tz)
        yesterday_str = (now - timedelta(days=1)).strftime("%d.%m.%Y")
        await self.generate_and_send_report(
            yesterday_str,
            is_monday=(now.weekday() == 0),
            update_penalties=True,
            send_to_log_thread=True
        )

    async def generate_and_send_report(
        self,
        date_str: str,
        is_monday: bool = False,
        update_penalties: bool = True,
        send_to_log_thread: bool = True
    ) -> tuple[discord.Embed, discord.Embed | None]:
        supports = await get_all_supports()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM daily_activity WHERE date_str = ?", (date_str,)) as cur:
                act_rows = [dict(r) for r in await cur.fetchall()]

        act_map = {(r["user_id"], r["slot"]): r for r in act_rows}
        slot_lines: dict[str, list[str]] = {s: [] for s in ALL_SLOTS}
        truants = []

        for sup in supports:
            uid = sup["user_id"]
            has_sup, has_exempt, _ = await check_support_status(self.bot, uid)
            if has_exempt or sup.get("is_exempt") == 1 or not has_sup:
                continue

            slot = sup.get("prime_time")
            if not slot or slot not in slot_lines:
                continue

            rec = act_map.get((uid, slot), {})
            mins = rec.get("minutes", 0)
            replaced_by = rec.get("replaced_by")

            in_vacation = False
            if sup.get("vacation_until"):
                try:
                    vac_dt = datetime.strptime(sup["vacation_until"], "%d.%m.%Y").date()
                    rep_dt = datetime.strptime(date_str, "%d.%m.%Y").date()
                    if rep_dt <= vac_dt:
                        in_vacation = True
                except Exception:
                    pass

            if in_vacation:
                slot_lines[slot].append(f"<@{uid}> 🌴")
                continue

            if sup.get("first_pt_shield", 0) == 1:
                slot_lines[slot].append(f"<@{uid}> 🛡️")
                if update_penalties:
                    await update_support_field(uid, "first_pt_shield", 0)
                continue

            if replaced_by:
                rep_rec = act_map.get((replaced_by, slot), {})
                rep_mins = max(mins, rep_rec.get("minutes", 0))
                icon = "✅" if rep_mins >= MIN_PRIME_MINUTES else "❌"
                slot_lines[slot].append(f"[{icon} - {rep_mins}] <@{uid}> (<@{replaced_by}>)")
                continue

            if mins >= MIN_PRIME_MINUTES:
                slot_lines[slot].append(f"[✅ - {mins}] <@{uid}>")
            else:
                slot_lines[slot].append(f"[❌ - {mins}] <@{uid}>")
                cur_misses = sup.get("weekly_misses", 0)
                new_misses = cur_misses + 1 if update_penalties else cur_misses
                if update_penalties:
                    await update_support_field(uid, "weekly_misses", new_misses)
                truants.append((uid, slot, mins, new_misses))

        for r in act_rows:
            if r.get("is_extra") == 1:
                s = r["slot"]
                uid = r["user_id"]
                has_sup, has_exempt, _ = await check_support_status(self.bot, uid)
                if not has_exempt and has_sup and s in slot_lines:
                    slot_lines[s].append(f"[✅ - {r['minutes']}] <@{uid}> ⚡")

        report_embed = discord.Embed(
            title=f"📊 Активность за сутки ({date_str})",
            color=0x2B2D31,
            timestamp=datetime.now(tz)
        )
        for slot in ALL_SLOTS:
            lines = slot_lines[slot]
            val = "\n".join(lines) if lines else "`Свободно`"
            report_embed.add_field(name=slot, value=val, inline=True)

        if send_to_log_thread:
            await send_log(self.bot, "reports", embed=report_embed)

        truant_embed = None
        if truants:
            truant_lines = [
                f"• <@{uid}> `{slot}` - `{mins} минут` - `Пропущено ПТ [{misses}]`"
                for uid, slot, mins, misses in truants
            ]
            truant_embed = discord.Embed(
                title="📋 Список прогульщиков",
                description="\n".join(truant_lines),
                color=0xED4245
            )
            if send_to_log_thread:
                await send_log(self.bot, "reports", embed=truant_embed)

        if update_penalties:
            for uid, slot, mins, _ in truants:
                user = self.bot.get_user(uid)
                if not user:
                    try:
                        user = await self.bot.fetch_user(uid)
                    except Exception:
                        user = None
                if user:
                    dm_embed = discord.Embed(
                        title="Привет!",
                        description=(
                            "Пожалуйста, объяснись, почему ты не досидел(а) следующие прайм-таймы:\n\n"
                            f"**{slot}** —\n"
                            f"{CODE_BLOCK}\n{mins} минут из требуемых 60\n{CODE_BLOCK}"
                        ),
                        color=0x2B2D31
                    )
                    try:
                        await user.send(embed=dm_embed, view=ExplainView(slot, mins, date_str))
                    except Exception:
                        pass

            if is_monday:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE supports SET weekly_misses = 0")
                    await db.commit()

        return report_embed, truant_embed


async def setup(bot: commands.Bot):
    await bot.add_cog(ReportsCog(bot))
