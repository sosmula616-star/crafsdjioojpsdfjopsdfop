import discord
from config import SUPPORT_ROLE_ID, EXEMPT_ROLE_IDS, MAIN_GUILD_ID, STAFF_GUILD_ID

MONITOR_BOT_INSTANCE: discord.Client | None = None

def set_monitor_bot_instance(client: discord.Client):
    global MONITOR_BOT_INSTANCE
    MONITOR_BOT_INSTANCE = client

def _extract_role_ids(member: discord.Member) -> set[int]:
    return {r.id for r in getattr(member, "roles", [])}

async def fetch_member_across_guilds(bot: discord.Client, user_id: int) -> list[discord.Member]:
    members: list[discord.Member] = []
    clients = [c for c in (MONITOR_BOT_INSTANCE, bot) if c is not None]

    seen_guilds = set()
    for client in clients:
        for g_id in (MAIN_GUILD_ID, STAFF_GUILD_ID):
            if (id(client), g_id) in seen_guilds:
                continue
            seen_guilds.add((id(client), g_id))
            guild = client.get_guild(g_id)
            if not guild:
                continue
            m = guild.get_member(user_id)
            if m is None:
                try:
                    m = await guild.fetch_member(user_id)
                except Exception:
                    m = None
            if m is not None:
                members.append(m)

    if not members:
        for client in clients:
            for guild in client.guilds:
                m = guild.get_member(user_id)
                if m is None:
                    try:
                        m = await guild.fetch_member(user_id)
                    except Exception:
                        m = None
                if m is not None:
                    members.append(m)
    return members

async def check_support_status(bot: discord.Client, user_id: int) -> tuple[bool, bool, discord.Member | discord.User | None]:
    members = await fetch_member_across_guilds(bot, user_id)
    all_roles: set[int] = set()
    primary_member = members[0] if members else None

    for m in members:
        r_ids = _extract_role_ids(m)
        all_roles.update(r_ids)
        if m.guild.id == MAIN_GUILD_ID:
            primary_member = m

    has_support = SUPPORT_ROLE_ID in all_roles
    has_exempt = bool(all_roles.intersection(EXEMPT_ROLE_IDS))

    if primary_member is None:
        try:
            primary_member = await bot.fetch_user(user_id)
        except Exception:
            primary_member = None

    return has_support, has_exempt, primary_member

async def can_use_support_commands(interaction: discord.Interaction) -> bool:
    if isinstance(interaction.user, discord.Member):
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild:
            return True
    has_sup, _, _ = await check_support_status(interaction.client, interaction.user.id)
    if not has_sup:
        await interaction.response.send_message(
            f"❌ У вас нет роли саппорта (`{SUPPORT_ROLE_ID}`), команды бота вам недоступны!",
            ephemeral=True
        )
        return False
    return True

async def validate_target_support(interaction: discord.Interaction, target_id: int, allow_exempt_view: bool = False) -> tuple[bool, discord.Member | discord.User | None]:
    has_sup, has_exempt, member_obj = await check_support_status(interaction.client, target_id)
    if member_obj is None:
        msg = f"❌ Пользователь с ID `{target_id}` не найден на сервере!"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False, None

    if not has_sup:
        msg = f"❌ У пользователя <@{target_id}> (`{target_id}`) нет роли саппорта (`{SUPPORT_ROLE_ID}`)! Применить команду невозможно."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False, None

    if has_exempt and not allow_exempt_view:
        msg = (
            f"⚠️ У пользователя <@{target_id}> есть исключающая роль "
            f"(`848876541009592341` / `1234034864228012095`). Норма ему не считается и команды ПТ к нему не применяются."
        )
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False, None

    return True, member_obj

def parse_user_id(raw_input: str) -> int | None:
    cleaned = "".join(ch for ch in raw_input.strip() if ch.isdigit())
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None
