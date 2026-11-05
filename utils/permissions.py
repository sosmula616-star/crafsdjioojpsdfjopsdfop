import discord
from config import SUPPORT_ROLE_ID, CURATOR_ROLE_IDS, MAIN_GUILD_ID, STAFF_GUILD_ID

MONITOR_BOT_INSTANCE = None

def set_monitor_bot_instance(client):
    global MONITOR_BOT_INSTANCE
    MONITOR_BOT_INSTANCE = client

def _extract_role_ids(member: discord.Member) -> set[int]:
    return {r.id for r in getattr(member, "roles", [])}

async def check_support_status(bot: discord.Client, user_id: int) -> tuple[bool, bool, discord.Member | discord.User | None]:
    all_roles: set[int] = set()
    primary_member = None

    if MONITOR_BOT_INSTANCE is not None:
        roles_from_mon, _ = await MONITOR_BOT_INSTANCE.get_member_roles_on_main(user_id)
        all_roles.update(roles_from_mon)

    for g_id in (MAIN_GUILD_ID, STAFF_GUILD_ID):
        guild = bot.get_guild(g_id)
        if not guild:
            continue
        m = guild.get_member(user_id)
        if m is None:
            try:
                m = await guild.fetch_member(user_id)
            except Exception:
                m = None
        if m is not None:
            if g_id == MAIN_GUILD_ID:
                all_roles.update(_extract_role_ids(m))
            if primary_member is None or g_id == MAIN_GUILD_ID:
                primary_member = m

    has_support = SUPPORT_ROLE_ID in all_roles
    has_curator = bool(all_roles.intersection(CURATOR_ROLE_IDS))

    if primary_member is None:
        try:
            primary_member = await bot.fetch_user(user_id)
        except Exception:
            primary_member = None

    return has_support, has_curator, primary_member

async def can_use_support_commands(interaction: discord.Interaction) -> bool:
    has_sup, has_cur, _ = await check_support_status(interaction.client, interaction.user.id)
    if has_sup or has_cur:
        return True
    if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
        return True

    msg = (
        f"❌ У вас нет роли Саппорта (`{SUPPORT_ROLE_ID}`) или Куратора на сервере `{MAIN_GUILD_ID}`! "
        "Команды бота вам недоступны."
    )
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)
    return False

async def can_use_curator_commands(interaction: discord.Interaction) -> bool:
    _, has_cur, _ = await check_support_status(interaction.client, interaction.user.id)
    if has_cur:
        return True
    if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
        return True

    msg = (
        "❌ У вас нет доступа к редактированию! "
        "Эту команду могут использовать только **Кураторы** (`848876541009592341` / `1234034864228012095`)."
    )
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)
    return False

async def validate_target_support(interaction: discord.Interaction, target_id: int, allow_exempt_view: bool = False) -> tuple[bool, discord.Member | discord.User | None]:
    has_sup, has_cur, member_obj = await check_support_status(interaction.client, target_id)
    if member_obj is None:
        msg = f"❌ Пользователь с ID `{target_id}` не найден в Discord!"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False, None

    if not has_sup:
        msg = f"❌ У пользователя <@{target_id}> (`{target_id}`) нет роли саппорта (`{SUPPORT_ROLE_ID}`) на сервере `{MAIN_GUILD_ID}`! Применить команду невозможно."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False, None

    if has_cur and not allow_exempt_view:
        msg = (
            f"⚠️ Пользователь <@{target_id}> является Куратором "
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
