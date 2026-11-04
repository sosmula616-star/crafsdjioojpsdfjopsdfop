import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from config import ALL_SLOTS
from database import (
    DB_PATH,
    ensure_support,
    get_all_supports,
    update_support_field,
    add_activity_minutes,
    now_str
)
from utils.profile_card import generate_profile_image
from utils.logger import send_log, resolve_token_emoji


class ExtraPTModal(discord.ui.Modal, title="Взять дополнительный ПТ"):
    slot_input = discord.ui.TextInput(
        label="Укажите часовой слот (например 18:00-19:00)",
        placeholder="18:00-19:00",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        slot = self.slot_input.value.strip()
        if slot not in ALL_SLOTS:
            return await interaction.response.send_message(
                "❌ Неверный слот! Пример: `18:00-19:00`", ephemeral=True
            )
        await add_activity_minutes(interaction.user.id, now_str(), slot, 0, is_extra=1)
        await send_log(
            interaction.client,
            "primes",
            f"⚡ Саппорт {interaction.user.mention} взял доп. ПТ на слот `{slot}`."
        )
        await interaction.response.send_message(
            f"⚡ Вы успешно записались на доп. ПТ `{slot}` сегодня!", ephemeral=True
        )


class PromoModal(discord.ui.Modal, title="Активация промокода"):
    code_input = discord.ui.TextInput(label="Введите промокод", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM promocodes WHERE code = ?", (code,)) as cur:
                promo = await cur.fetchone()
            if not promo or promo["uses_left"] <= 0:
                return await interaction.response.send_message("❌ Промокод не найден или закончился!", ephemeral=True)

            async with db.execute(
                "SELECT 1 FROM promo_used WHERE user_id = ? AND code = ?", (interaction.user.id, code)
            ) as cur:
                if await cur.fetchone():
                    return await interaction.response.send_message("❌ Вы уже активировали этот промокод!", ephemeral=True)

            await db.execute("INSERT INTO promo_used (user_id, code) VALUES (?, ?)", (interaction.user.id, code))
            await db.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            await db.execute("UPDATE supports SET balance = balance + ? WHERE user_id = ?", (promo["reward"], interaction.user.id))
            await db.commit()

        em = resolve_token_emoji(interaction.client)
        await interaction.response.send_message(
            f"🎉 Промокод активирован! Начислено **{promo['reward']}** {em}", ephemeral=True
        )


class SupportVacationModal(discord.ui.Modal, title="Запрос отпуска"):
    until_date = discord.ui.TextInput(
        label="До какой даты нужен отпуск (ДД.ММ.ГГГГ)",
        placeholder="15.05.2026",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        val = self.until_date.value.strip()
        await update_support_field(interaction.user.id, "vacation_until", val)
        await send_log(
            interaction.client,
            "primes",
            f"🌴 Саппорт {interaction.user.mention} оформил отпуск до `{val}`."
        )
        await interaction.response.send_message(f"🌴 Отпуск до `{val}` успешно установлен!", ephemeral=True)


class ShopSelect(discord.ui.Select):
    def __init__(self, items: list[dict]):
        options = [
            discord.SelectOption(label=i["name"], description=f"Цена: {i['price']} токенов", value=str(i["id"]))
            for i in items
        ]
        super().__init__(placeholder="Выберите товар для покупки...", options=options)
        self.items_map = {str(i["id"]): i for i in items}

    async def callback(self, interaction: discord.Interaction):
        item = self.items_map[self.values[0]]
        data = await ensure_support(interaction.user.id)
        if data["balance"] < item["price"]:
            return await interaction.response.send_message("❌ Недостаточно токенов!", ephemeral=True)

        new_bal = data["balance"] - item["price"]
        await update_support_field(interaction.user.id, "balance", new_bal)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, bought_at) VALUES (?, ?, ?)",
                (interaction.user.id, item["name"], now_str())
            )
            await db.commit()

        em = resolve_token_emoji(interaction.client)
        await send_log(
            interaction.client,
            "shop",
            f"🛒 {interaction.user.mention} купил **{item['name']}** за **{item['price']}** {em}."
        )
        await interaction.response.send_message(
            f"✅ Вы купили **{item['name']}** за **{item['price']}** {em}!", ephemeral=True
        )


class ProfileView(discord.ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=600)
        self.member = member

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        data = await ensure_support(self.member.id)
        av_bytes = await self.member.display_avatar.read()
        card = generate_profile_image(self.member.name, data, av_bytes)
        file = discord.File(card, filename="profile.png")
        await interaction.edit_original_response(
            content=f"**Профиль саппорта - {self.member.name}**",
            attachments=[file],
            view=self
        )

    @discord.ui.button(label="⇄ Взять замену", style=discord.ButtonStyle.secondary, row=1)
    async def swap_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM swap_requests WHERE taken_by IS NULL AND date_str = ?", (now_str(),)
            ) as cur:
                req = await cur.fetchone()
            if not req:
                return await interaction.response.send_message(
                    "ℹ️ На сегодня нет активных запросов на замену.", ephemeral=True
                )
            await db.execute(
                "UPDATE swap_requests SET taken_by = ? WHERE id = ?", (interaction.user.id, req["id"])
            )
            await db.execute('''
                INSERT INTO daily_activity (user_id, date_str, slot, minutes, replaced_by)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(user_id, date_str, slot) DO UPDATE SET replaced_by = excluded.replaced_by
            ''', (req["requester_id"], req["date_str"], req["slot"], interaction.user.id))
            await db.execute(
                "UPDATE supports SET swaps_taken = swaps_taken + 1 WHERE user_id = ?",
                (interaction.user.id,)
            )
            await db.commit()

        await send_log(
            interaction.client,
            "swaps",
            f"🤝 {interaction.user.mention} взял замену за <@{req['requester_id']}> на слот `{req['slot']}`."
        )
        await interaction.response.send_message(
            f"✅ Вы взяли замену за <@{req['requester_id']}> на слот `{req['slot']}`!", ephemeral=True
        )

    @discord.ui.button(label="🕒 Взять доп. ПТ", style=discord.ButtonStyle.secondary, row=1)
    async def extra_pt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExtraPTModal())

    @discord.ui.button(label="🕒 Прайм-таймы", style=discord.ButtonStyle.secondary, row=1)
    async def primes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        supports = await get_all_supports()
        lines = [
            f"`{s['prime_time']}` — <@{s['user_id']}>"
            for s in supports if s.get("prime_time")
        ]
        text = "\n".join(lines) if lines else "Нет назначенных прайм-таймов."
        await interaction.response.send_message(f"📅 **Текущие прайм-таймы:**\n{text}", ephemeral=True)

    @discord.ui.button(label="📋 Задания", style=discord.ButtonStyle.secondary, row=1)
    async def tasks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        em = resolve_token_emoji(interaction.client)
        embed = discord.Embed(
            title="📋 Ежедневные задания саппорта",
            description=(
                f"1. Отсидеть свой прайм-тайм (минимум 47 минут) — **+25** {em}\n"
                f"2. Принять замену другого саппорта — **+30** {em}\n"
                f"3. Провести 10 допусков в прихожей — **+20** {em}"
            ),
            color=0x2B2D31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎫 Промокод", style=discord.ButtonStyle.secondary, row=2)
    async def promo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PromoModal())

    @discord.ui.button(label="🛒 Магазин", style=discord.ButtonStyle.secondary, row=3)
    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM shop_items") as cur:
                items = [dict(r) for r in await cur.fetchall()]
        v = discord.ui.View()
        v.add_item(ShopSelect(items))
        await interaction.response.send_message("🛒 **Магазин саппортов:**", view=v, ephemeral=True)

    @discord.ui.button(label="📦 Инвентарь", style=discord.ButtonStyle.secondary, row=3)
    async def inv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM inventory WHERE user_id = ?", (interaction.user.id,)) as cur:
                rows = await cur.fetchall()
        if not rows:
            return await interaction.response.send_message("📦 Ваш инвентарь пуст.", ephemeral=True)
        items_txt = "\n".join(f"• **{r['item_name']}** (куплено `{r['bought_at']}`)" for r in rows)
        await interaction.response.send_message(f"📦 **Ваш инвентарь:**\n{items_txt}", ephemeral=True)

    @discord.ui.button(label="🌴 Отпуск", style=discord.ButtonStyle.secondary, row=3)
    async def vacation_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportVacationModal())


class SupportProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    support_group = app_commands.Group(name="support", description="Команды для саппортов")

    @support_group.command(name="profile", description="Открыть профиль саппорта")
    async def support_profile(self, interaction: discord.Interaction):
        await interaction.response.defer()
        data = await ensure_support(interaction.user.id)
        av_bytes = await interaction.user.display_avatar.read()
        card = generate_profile_image(interaction.user.name, data, av_bytes)
        file = discord.File(card, filename="profile.png")
        view = ProfileView(interaction.user)
        await interaction.followup.send(
            content=f"**Профиль саппорта - {interaction.user.name}**",
            file=file,
            view=view
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SupportProfileCog(bot))
