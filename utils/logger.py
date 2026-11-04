import discord
from config import LOG_CHANNEL_ID, THREAD_NAMES, TOKEN_EMOJI
from database import get_setting, set_setting, get_saved_thread_id, save_thread_id

def resolve_token_emoji(bot_or_guild=None) -> str:
    return TOKEN_EMOJI

async def get_bound_log_channel(bot: discord.Client) -> discord.TextChannel | None:
    saved_id = await get_setting("log_channel_id")
    ch_id = int(saved_id) if saved_id else LOG_CHANNEL_ID
    if not ch_id:
        return None
    ch = bot.get_channel(ch_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(ch_id)
        except Exception:
            return None
    return ch if isinstance(ch, discord.TextChannel) else None

async def ensure_all_log_threads(bot: discord.Client, channel: discord.TextChannel) -> dict[str, discord.Thread]:
    await set_setting("log_channel_id", str(channel.id))

    existing_by_name: dict[str, discord.Thread] = {}
    for t in channel.threads:
        existing_by_name[t.name] = t

    try:
        async for t in channel.archived_threads(limit=100):
            if t.name not in existing_by_name:
                existing_by_name[t.name] = t
    except Exception:
        pass

    result: dict[str, discord.Thread] = {}
    for category, thread_name in THREAD_NAMES.items():
        thread = existing_by_name.get(thread_name)
        if thread is None:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=10080
            )
        elif thread.archived:
            try:
                await thread.edit(archived=False)
            except Exception:
                pass

        await save_thread_id(category, thread.id)
        result[category] = thread

    return result

async def get_or_create_thread(bot: discord.Client, category: str) -> discord.Thread | None:
    thread_name = THREAD_NAMES.get(category)
    if not thread_name:
        return None

    thread_id = await get_saved_thread_id(category)
    if thread_id:
        th = bot.get_channel(thread_id)
        if th is None:
            try:
                th = await bot.fetch_channel(thread_id)
            except Exception:
                th = None
        if isinstance(th, discord.Thread):
            if th.archived:
                try:
                    await th.edit(archived=False)
                except Exception:
                    pass
            return th

    channel = await get_bound_log_channel(bot)
    if not channel:
        return None

    threads = await ensure_all_log_threads(bot, channel)
    return threads.get(category)

async def send_log(bot: discord.Client, category: str, content: str = None, embed: discord.Embed = None):
    thread = await get_or_create_thread(bot, category)
    if not thread:
        return None
    return await thread.send(content=content, embed=embed)
