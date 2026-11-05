import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import pytz
from config import TIMEZONE, ALL_SLOTS, MAX_WARNS
from database import (
    ensure_support,
    get_all_supports,
    update_support_field,
    change_warns,
    delete_support,
    set_activity_minutes,
    now_str,
    DB_PATH
)
import aiosqlite
from utils.logger import send_log, resolve_token_emoji, ensure_all_log_threads
from utils.permissions import can_use_support_commands, validate_target_support, parse_user_id

def build_admin_embed(user_obj: discord.Member | discord.User, data: dict, emoji_str: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"Админ панель — {user_obj.name}",
        color=0x2B2D31
    )
    pt = data.get("prime_time") or "Не назначен"
    hire_date = data.get("hire_date") or now_str()
    balance = data.get("balance", 0)
    warns = data.get("warns", 0)

    desc = (
        f"Саппорт: <@{user_obj.id}> (`{user_obj.id}`)\n"
        f"Прайм-тайм: `{pt}`\n"
        f"Дата принятия: `{hire_date}`\n"
        f"Выговоры: **`{warns} / {MAX_WARNS}`**\n"
        f"Баланс: **{balance}** {emoji_str}"
    )
    if data.get("probation_until"):
        desc += f"\nИсп. срок до: `{data['probation_until']}`"
    if data.get("vacation_until"):
        desc += f"\nОтпуск до: `{data['vacation_until']}`"

    embed.description = desc
    embed.set_thumbnail(url=user_obj.display_avatar.url)
    return embed


async def build_pt_picker_embed(target: discord.Member | discord.User, current_slot: str | None) -> discord.Embed:
    supports = await get_all_supports()
    counts = {s: 0 for s in ALL_SLOTS}
    for s in supports:
        pt = s.get("prime_time")
        if pt in counts and not s.get("is_exempt"):
            counts[pt] += 1

    embed = discord.Embed(
        title=f"🕒 Назначение прайм-тайма — {target.display_name}",
        description=(
            f"Саппорт: <@{target.id}> (`{target.id}`)\n"
            f"Текущий прайм-тайм: **`{current_slot or 'Не назначен'}`**\n\n"
            "Выберите нужный часовой слот в меню ниже:"
        ),
        color=0x5865F2
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


class SlotSelect(discord.ui.Select):
    def __init__(self, target: discord.Member | discord.User, slots_slice: list[str], placeholder: str, counts: dict[str, int], current_slot: str | None, parent_panel: "AdminPanelView | None" = None):
        self.target = target
        self.parent_panel = parent_panel
        options = []
        for slot in slots_slice:
            cnt = counts.get(slot, 0)
            desc = f"Занято мест: {cnt}" if cnt > 0 else "Свободно (0 чел.)"
            options.append(
                discord.SelectOption(
                    label=slot,
                    value=slot,
                    description=desc,
                    emoji="🕒",
                    default=(slot == current_slot)
                )
            )
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen_slot = self.values[0]
        await ensure_support(self.target.id)
        await update_support_field(self.target.id, "prime_time", chosen_slot)
        await send_log(
            interaction.client,
            "primes",
            f"🕒 {interaction.user.mention} установил прайм-тайм `{chosen_slot}` для <@{self.target.id}>."
        )

        supports = await get_all_supports()
        counts = {s: 0 for s in ALL_SLOTS}
        for s in supports:
            if s.get("prime_time") in counts and not s.get("is_exempt"):
                counts[s["prime_time"]] += 1

        new_view = PrimeTimePickerView(self.target, counts, chosen_slot, self.parent_panel)
        new_embed = await build_pt_picker_embed(self.target, chosen_slot)
        await interaction.response.edit_message(
            content=f"✅ Прайм-тайм для <@{self.target.id}> успешно изменён на **`{chosen_slot}`**!",
            embed=new_embed,
            view=new_view
        )


class PrimeTimePickerView(discord.ui.View):
    def __init__(self, target: discord.Member | discord.User, counts: dict[str, int], current_slot: str | None, parent_panel: "AdminPanelView | None" = None):
        super().__init__(timeout=600)
        self.target = target
        self.parent_panel = parent_panel

        morning_slots = ALL_SLOTS[:12]
        evening_slots = ALL_SLOTS[12:]

        self.add_item(SlotSelect(
            target, morning_slots,
            "🌙 Ночь / Утро (00:00 — 12:00)",
            counts, current_slot, parent_panel
        ))
        self.add_item(SlotSelect(
            target, evening_slots,
            "☀️ День / Вечер (12:00 — 00:00)",
            counts, current_slot, parent_panel
        ))

    @discord.ui.button(label="Снять прайм-тайм", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def clear_pt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ensure_support(self.target.id)
        await update_support_field(self.target.id, "prime_time", None)
        await send_log(
            interaction.client,
            "primes",
            f"🗑️ {interaction.user.mention} снял прайм-тайм у <@{self.target.id}>."
        )
        supports = await get_all_supports()
        counts = {s: 0 for s in ALL_SLOTS}
        for s in supports:
            if s.get("prime_time") in counts and not s.get("is_exempt"):
                counts[s["prime_time"]] += 1

        new_view = PrimeTimePickerView(self.target, counts, None, self.parent_panel)
        new_embed = await build_pt_picker_embed(self.target, None)
        await interaction.response.edit_message(
            content=f"🗑️ Прайм-тайм у <@{self.target.id}> удалён.",
            embed=new_embed,
            view=new_view
        )

    @discord.ui.button(label="⬅️ В админ-панель", style=discord.ButtonStyle.secondary, row=2)
    async def back_to_admin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await ensure_support(self.target.id)
        view = AdminPanelView(self.target, data)
        em = resolve_token_emoji(interaction.client)
        embed = build_admin_embed(self.target, data, em)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


class HireDateModal(discord.ui.Modal, title="Изменить дату принятия"):
    date_input = discord.ui.TextInput(
        label="Дата принятия (ДД.ММ.ГГГГ)",
        placeholder="28.04.2026",
        min_length=8,
        max_length=10
    )

    def __init__(self, target: discord.Member | discord.User, view: "AdminPanelView"):
        super().__init__()
        self.target = target
        self.panel_view = view

    async def on_submit(self, interaction: discord.Interaction):
        val = self.date_input.value.strip()
        try:
            datetime.strptime(val, "%d.%m.%Y")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Неверный формат даты! Используйте `ДД.ММ.ГГГГ`.", ephemeral=True
            )
        await update_support_field(self.target.id, "hire_date", val)
        data = await ensure_support(self.target.id)
        self.panel_view.sync_styles(data)
        em = resolve_token_emoji(interaction.client)
        await interaction.response.edit_message(
            embed=build_admin_embed(self.target, data, em),
            view=self.panel_view
        )


class VacationModal(discord.ui.Modal, title="Выдать отпуск саппорту"):
    until_input = discord.ui.TextInput(
        label="До какой даты отпуск (ДД.ММ.ГГГГ)",
        placeholder="10.05.2026",
        min_length=8,
        max_length=10
    )

    def __init__(self, target: discord.Member | discord.User, view: "AdminPanelView"):
        super().__init__()
        self.target = target
        self.panel_view = view

    async def on_submit(self, interaction: discord.Interaction):
        val = self.until_input.value.strip()
        try:
            datetime.strptime(val, "%d.%m.%Y")
        except ValueError:
            return await interaction.response.send_message(
                "❌ Неверный формат даты! Используйте `ДД.ММ.ГГГГ`.", ephemeral=True
            )
        await update_support_field(self.target.id, "vacation_until", val)
        data = await ensure_support(self.target.id)
        self.panel_view.sync_styles(data)
        em = resolve_token_emoji(interaction.client)
        await interaction.response.edit_message(
            embed=build_admin_embed(self.target, data, em),
            view=self.panel_view
        )


class AdminPanelView(discord.ui.View):
    def __init__(self, target: discord.Member | discord.User, data: dict):
        super().__init__(timeout=600)
        self.target = target
        self.sync_styles(data)

    def sync_styles(self, data: dict):
        if data.get("probation_until"):
            self.probation_btn.style = discord.ButtonStyle.success
        else:
            self.probation_btn.style = discord.ButtonStyle.secondary

        if data.get("vacation_until"):
            self.vacation_btn.style = discord.ButtonStyle.success
        else:
            self.vacation_btn.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="Дата принятия", style=discord.ButtonStyle.primary, row=0)
    async def hire_date_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HireDateModal(self.target, self))

    @discord.ui.button(label="Исп.срок", style=discord.ButtonStyle.secondary, row=0)
    async def probation_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await ensure_support(self.target.id)
        if data.get("probation_until"):
            await update_support_field(self.target.id, "probation_until", None)
        else:
            tz = pytz.timezone(TIMEZONE)
            until = (datetime.now(tz) + timedelta(days=7)).strftime("%d.%m.%Y")
            await update_support_field(self.target.id, "probation_until", until)

        new_data = await ensure_support(self.target.id)
        self.sync_styles(new_data)
        em = resolve_token_emoji(interaction.client)
        await interaction.response.edit_message(
            embed=build_admin_embed(self.target, new_data, em),
            view=self
        )

    @discord.ui.button(label="Отпуск", style=discord.ButtonStyle.secondary, row=0)
    async def vacation_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await ensure_support(self.target.id)
        if data.get("vacation_until"):
            await update_support_field(self.target.id, "vacation_until", None)
            new_data = await ensure_support(self.target.id)
            self.sync_styles(new_data)
            em = resolve_token_emoji(interaction.client)
            await interaction.response.edit_message(
                embed=build_admin_embed(self.target, new_data, em),
                view=self
            )
        else:
            await interaction.response.send_modal(VacationModal(self.target, self))

    @discord.ui.button(label="🕒 Прайм-тайм", style=discord.ButtonStyle.primary, row=1)
    async def pt_picker_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await ensure_support(self.target.id)
        supports = await get_all_supports()
        counts = {s: 0 for s in ALL_SLOTS}
        for s in supports:
            if s.get("prime_time") in counts and not s.get("is_exempt"):
                counts[s["prime_time"]] += 1

        picker_view = PrimeTimePickerView(self.target, counts, data.get("prime_time"), self)
        picker_embed = await build_pt_picker_embed(self.target, data.get("prime_time"))
        await interaction.response.edit_message(embed=picker_embed, view=picker_view)

    @discord.ui.button(label="+1 Выговор", style=discord.ButtonStyle.secondary, emoji="⚠️", row=1)
    async def add_warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_w = await change_warns(self.target.id, delta=1)
        await send_log(
            interaction.client,
            "warns",
            f"⚠️ {interaction.user.mention} выдал выговор <@{self.target.id}> через админ-панель. Теперь: **`{new_w}/{MAX_WARNS}`**."
        )
        new_data = await ensure_support(self.target.id)
        em = resolve_token_emoji(interaction.client)
        await interaction.response.edit_message(embed=build_admin_embed(self.target, new_data, em), view=self)

    @discord.ui.button(label="-1 Выговор", style=discord.ButtonStyle.secondary, row=1)
    async def rem_warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_w = await change_warns(self.target.id, delta=-1)
        await send_log(
            interaction.client,
            "warns",
            f"✅ {interaction.user.mention} снял выговор у <@{self.target.id}> через админ-панель. Теперь: **`{new_w}/{MAX_WARNS}`**."
        )
        new_data = await ensure_support(self.target.id)
        em = resolve_token_emoji(interaction.client)
        await interaction.response.edit_message(embed=build_admin_embed(self.target, new_data, em), view=self)

    @discord.ui.button(label="Удалить из БД", style=discord.ButtonStyle.danger, row=2)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_support(self.target.id)
        await send_log(
            interaction.client,
            "removals",
            f"🗑️ **{interaction.user.mention}** удалил саппорта <@{self.target.id}> из базы данных."
        )
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"✅ Саппорт <@{self.target.id}> удалён из БД.",
            embed=None,
            view=self
        )


class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Админ-команды управления саппортами")
    prime_group = app_commands.Group(name="prime", description="Управление прайм-таймами")

    @app_commands.command(name="set_logs", description="Привязать канал #логи (бот сам создаст в нём все 9 веток)")
    @app_commands.describe(канал="Текстовый канал для логов и отчётов")
    @app_commands.default_permissions(manage_guild=True)
    async def set_logs_cmd(self, interaction: discord.Interaction, канал: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        threads = await ensure_all_log_threads(self.bot, канал)
        mentions = ", ".join(t.mention for t in threads.values())
        await interaction.followup.send(
            f"✅ Канал {канал.mention} привязан! Все ветки готовы:\n{mentions}",
            ephemeral=True
        )

    @admin_group.command(name="panel", description="Управление выбранным саппортом (по упоминанию или ID)")
    @app_commands.describe(саппорт="Упоминание @саппорта или его Discord ID")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_panel(self, interaction: discord.Interaction, саппорт: str):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, target_obj = await validate_target_support(interaction, uid, allow_exempt_view=False)
        if not ok:
            return

        data = await ensure_support(uid)
        view = AdminPanelView(target_obj, data)
        em = resolve_token_emoji(self.bot)
        embed = build_admin_embed(target_obj, data, em)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="award", description="Выдать токены саппорту (по упоминанию или ID)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта", количество="Сколько токенов", причина="Причина выдачи")
    @app_commands.default_permissions(manage_guild=True)
    async def award_cmd(self, interaction: discord.Interaction, саппорт: str, количество: int, причина: str = "Не указана"):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        new_bal = data["balance"] + количество
        await update_support_field(uid, "balance", new_bal)
        em = resolve_token_emoji(self.bot)
        await send_log(
            self.bot,
            "tokens",
            f"➕ {interaction.user.mention} выдал **{количество}** {em} саппорту <@{uid}>. Причина: `{причина}` (Баланс: `{new_bal}` {em})"
        )
        await interaction.response.send_message(
            f"✅ Выдано **{количество}** {em} для <@{uid}>. Текущий баланс: **{new_bal}** {em}",
            ephemeral=True
        )

    @app_commands.command(name="take", description="Забрать токены у саппорта (по упоминанию или ID)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта", количество="Сколько токенов", причина="Причина")
    @app_commands.default_permissions(manage_guild=True)
    async def take_cmd(self, interaction: discord.Interaction, саппорт: str, количество: int, причина: str = "Не указана"):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        new_bal = max(0, data["balance"] - количество)
        await update_support_field(uid, "balance", new_bal)
        em = resolve_token_emoji(self.bot)
        await send_log(
            self.bot,
            "tokens",
            f"➖ {interaction.user.mention} забрал **{количество}** {em} у саппорта <@{uid}>. Причина: `{причина}` (Баланс: `{new_bal}` {em})"
        )
        await interaction.response.send_message(
            f"✅ Забрано **{количество}** {em} у <@{uid}>. Текущий баланс: **{new_bal}** {em}",
            ephemeral=True
        )

    @prime_group.command(name="set", description="Открыть панель назначения прайм-тайма саппорту (по упоминанию или ID)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта")
    @app_commands.default_permissions(manage_guild=True)
    async def prime_set(self, interaction: discord.Interaction, саппорт: str):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, target_obj = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        supports = await get_all_supports()
        counts = {s: 0 for s in ALL_SLOTS}
        for s in supports:
            if s.get("prime_time") in counts and not s.get("is_exempt"):
                counts[s["prime_time"]] += 1

        view = PrimeTimePickerView(target_obj, counts, data.get("prime_time"))
        embed = await build_pt_picker_embed(target_obj, data.get("prime_time"))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @prime_group.command(name="remove", description="Удалить прайм-тайм у саппорта (по упоминанию или ID)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта")
    @app_commands.default_permissions(manage_guild=True)
    async def prime_remove(self, interaction: discord.Interaction, саппорт: str):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        await ensure_support(uid)
        await update_support_field(uid, "prime_time", None)
        await send_log(
            self.bot,
            "primes",
            f"🗑️ {interaction.user.mention} удалил прайм-тайм у <@{uid}>."
        )
        await interaction.response.send_message(
            f"✅ Прайм-тайм у <@{uid}> удалён.", ephemeral=True
        )

    @prime_group.command(name="list", description="Таблица прайм-таймов всех саппортов")
    async def prime_list(self, interaction: discord.Interaction):
        if not await can_use_support_commands(interaction):
            return

        supports = await get_all_supports()
        by_slot: dict[str, list[str]] = {slot: [] for slot in ALL_SLOTS}
        for s in supports:
            if s.get("is_exempt"):
                continue
            slot = s.get("prime_time")
            if slot in by_slot:
                suffix = " 🌴" if s.get("vacation_until") else ""
                by_slot[slot].append(f"<@{s['user_id']}>{suffix}")

        embed = discord.Embed(title="📅 Таблица прайм-таймов", color=0x2B2D31)
        for slot in ALL_SLOTS:
            users = by_slot[slot]
            val = "\n".join(users) if users else "`Свободно`"
            embed.add_field(name=slot, value=val, inline=True)

        await interaction.response.send_message(embed=embed)

    @prime_group.command(name="add", description="Засчитать ПТ саппорту (по умолчанию за сегодня)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта", дата="Дата ДД.ММ.ГГГГ (необязательно)")
    @app_commands.default_permissions(manage_guild=True)
    async def prime_add(self, interaction: discord.Interaction, саппорт: str, дата: str = None):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        slot = data.get("prime_time")
        if not slot:
            return await interaction.response.send_message(
                "❌ У этого саппорта не назначен прайм-тайм!", ephemeral=True
            )
        target_date = дата.strip() if дата else now_str()
        await set_activity_minutes(uid, target_date, slot, 60, is_extra=0)
        await send_log(
            self.bot,
            "reports",
            f"✅ {interaction.user.mention} вручную засчитал ПТ (`{slot}` за `{target_date}`) саппорту <@{uid}>."
        )
        await interaction.response.send_message(
            f"✅ ПТ `{slot}` за `{target_date}` засчитан (60 мин) для <@{uid}>.",
            ephemeral=True
        )

    @app_commands.command(name="miss", description="Вычесть пропуск из отчётов (уменьшить счётчик прогулов)")
    @app_commands.describe(саппорт="Упоминание или ID саппорта", количество="Сколько прогулов вычесть (по умолчанию 1)")
    @app_commands.default_permissions(manage_guild=True)
    async def miss_cmd(self, interaction: discord.Interaction, саппорт: str, количество: int = 1):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        new_misses = max(0, data.get("weekly_misses", 0) - количество)
        await update_support_field(uid, "weekly_misses", new_misses)
        await send_log(
            self.bot,
            "reports",
            f"📉 {interaction.user.mention} вычел `{количество}` прогул(ов) у <@{uid}>. Теперь: `[{new_misses}]`."
        )
        await interaction.response.send_message(
            f"✅ У <@{uid}> вычтено `{количество}` прогулов. Текущий счётчик: `[{new_misses}]`.",
            ephemeral=True
        )

    @app_commands.command(name="swap_as", description="Запросить замену от имени саппорта")
    @app_commands.describe(саппорт="Упоминание или ID саппорта", дата="Дата ДД.ММ.ГГГГ (по умолчанию сегодня)")
    @app_commands.default_permissions(manage_guild=True)
    async def swap_as_cmd(self, interaction: discord.Interaction, саппорт: str, дата: str = None):
        uid = parse_user_id(саппорт)
        if not uid:
            return await interaction.response.send_message("❌ Укажите корректное упоминание или ID!", ephemeral=True)

        ok, _ = await validate_target_support(interaction, uid)
        if not ok:
            return

        data = await ensure_support(uid)
        slot = data.get("prime_time")
        if not slot:
            return await interaction.response.send_message(
                "❌ У саппорта нет назначенного ПТ!", ephemeral=True
            )
        target_date = дата.strip() if дата else now_str()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO swap_requests (requester_id, date_str, slot) VALUES (?, ?, ?)",
                (uid, target_date, slot)
            )
            await db.commit()

        await send_log(
            self.bot,
            "swaps",
            f"🔄 Запрошена замена для <@{uid}> на слот `{slot}` (`{target_date}`) (создал: {interaction.user.mention})."
        )
        await interaction.response.send_message(
            f"✅ Запрос на замену от имени <@{uid}> (`{slot}`, `{target_date}`) создан!",
            ephemeral=True
        )

    @app_commands.command(name="dm", description="Отправить сообщение в ЛС от имени бота")
    @app_commands.describe(пользователь="Кому отправить", текст="Текст сообщения")
    @app_commands.default_permissions(manage_guild=True)
    async def dm_cmd(self, interaction: discord.Interaction, пользователь: discord.Member, текст: str):
        try:
            await пользователь.send(текст)
            await interaction.response.send_message(
                f"✅ Сообщение успешно отправлено в ЛС {пользователь.mention}.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Не удалось отправить ЛС пользователю: {e}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))
