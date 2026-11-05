import asyncio
import json
import re
import time
import aiohttp
from config import (
    MONITOR_TOKEN,
    MAIN_GUILD_ID,
    SUPPORT_ROLE_ID,
    CURATOR_ROLE_IDS,
    LOBBY_CHANNELS,
    REPRIMAND_CHANNEL_ID,
    TICKETS_CHANNEL_ID,
    MAX_WARNS
)
from database import (
    init_db,
    ensure_support,
    update_support_field,
    add_activity_minutes,
    change_warns,
    mark_event_processed,
    increment_stat,
    now_str,
    current_slot_str
)
from utils.logger import send_log

class MonitorBot:
    def __init__(self, main_bot=None):
        self.main_bot = main_bot
        self.token = ""
        self.is_bot = True  # Всегда True для бот-токена
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self._closed = False

        self.voice_states: dict[int, int] = {}
        self.member_roles: dict[int, tuple[set[int], float]] = {}
        self.name_to_id: dict[str, int] = {}
        self.seq = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
        }

    async def _detect_token_mode(self) -> bool:
        if not self.token:
            return False
        try:
            async with self.session.get("https://discord.com/api/v10/users/@me", headers=self._headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[+] Монитор авторизован как бот: {data.get('username')} (ID: {data.get('id')})")
                    return True
                elif resp.status == 401:
                    print("❌ [МОНИТОР] Токен недействителен (401 Unauthorized)! Проверьте MONITOR_TOKEN в .env")
                    return False
        except Exception as e:
            print(f"[Monitor Auth] Ошибка подключения: {e}")
        return False

    async def get_member_roles_on_main(self, user_id: int) -> tuple[set[int], dict | None]:
        now_ts = time.time()
        cached = self.member_roles.get(user_id)
        if cached and (now_ts - cached[1] < 120):
            return cached[0], None

        if not self.session or self.session.closed or not self.token:
            return (cached[0] if cached else set()), None

        url = f"https://discord.com/api/v10/guilds/{MAIN_GUILD_ID}/members/{user_id}"
        try:
            async with self.session.get(url, headers=self._headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    roles = {int(r) for r in data.get("roles", [])}
                    self.member_roles[user_id] = (roles, now_ts)
                    user_obj = data.get("user", {})
                    for key in ("username", "global_name"):
                        if user_obj.get(key):
                            self.name_to_id[user_obj[key].lower()] = user_id
                    if data.get("nick"):
                        self.name_to_id[data["nick"].lower()] = user_id
                    return roles, data
                elif resp.status == 404:
                    self.member_roles[user_id] = (set(), now_ts)
                    return set(), None
        except Exception as e:
            print(f"[Monitor API] Ошибка проверки ролей {user_id}: {e}")

        return (cached[0] if cached else set()), None

    def _cache_member_payload(self, member_data: dict):
        user = member_data.get("user") or {}
        uid_str = user.get("id")
        if not uid_str:
            return
        uid = int(uid_str)
        roles = {int(r) for r in member_data.get("roles", [])}
        self.member_roles[uid] = (roles, time.time())
        for key in ("username", "global_name"):
            if user.get(key):
                self.name_to_id[user[key].lower()] = uid
        if member_data.get("nick"):
            self.name_to_id[member_data["nick"].lower()] = uid

    async def _voice_minute_loop(self):
        await asyncio.sleep(10)
        while not self._closed:
            try:
                date_str = now_str()
                slot_str = current_slot_str()

                active_users = [
                    (uid, ch_id)
                    for uid, ch_id in list(self.voice_states.items())
                    if ch_id in LOBBY_CHANNELS
                ]

                for uid, ch_id in active_users:
                    roles, _ = await self.get_member_roles_on_main(uid)
                    has_support = SUPPORT_ROLE_ID in roles
                    has_curator = bool(roles.intersection(CURATOR_ROLE_IDS))

                    if not has_support:
                        continue

                    if has_curator:
                        await ensure_support(uid)
                        await update_support_field(uid, "is_exempt", 1)
                        continue

                    await ensure_support(uid)
                    await update_support_field(uid, "is_exempt", 0)
                    await add_activity_minutes(uid, date_str, slot_str, 1)
            except Exception as e:
                print(f"[Monitor Voice Loop] Ошибка: {e}")

            await asyncio.sleep(60)

    async def _poll_channels_loop(self):
        await asyncio.sleep(15)
        reprimand_url = f"https://discord.com/api/v10/channels/{REPRIMAND_CHANNEL_ID}/messages?limit=10"
        tickets_url = f"https://discord.com/api/v10/channels/{TICKETS_CHANNEL_ID}/messages?limit=10"
        
        while not self._closed:
            try:
                if self.session and not self.session.closed:
                    # Обработка выговоров
                    async with self.session.get(reprimand_url, headers=self._headers()) as resp:
                        if resp.status == 200:
                            for msg in reversed(await resp.json()):
                                await self._handle_raw_message(msg)
                        elif resp.status in (401, 403):
                            print(f"[Monitor Poll] Нет доступа к каналу выговоров: {resp.status}")
                    
                    # Обработка закрытых тикетов
                    async with self.session.get(tickets_url, headers=self._headers()) as resp:
                        if resp.status == 200:
                            for msg in reversed(await resp.json()):
                                await self._handle_ticket_message(msg)
                        elif resp.status in (401, 403):
                            print(f"[Monitor Poll] Нет доступа к каналу тикетов: {resp.status}")
            except Exception as e:
                print(f"[Monitor Poll] Ошибка: {e}")
            
            await asyncio.sleep(30)

    def _extract_raw_embed_text(self, embed: dict) -> str:
        parts = []
        if embed.get("title"):
            parts.append(str(embed["title"]))
        if embed.get("description"):
            parts.append(str(embed["description"]))
        for f in embed.get("fields", []):
            parts.append(f"{f.get('name', '')}\n{f.get('value', '')}")
        return "\n".join(parts)

    async def _resolve_target_user_from_reprimand(self, text: str) -> int | None:
        mentions = re.findall(r"<@!?(\d{15,21})>", text)
        if len(mentions) >= 2:
            return int(mentions[1])

        m_id = re.search(r"пользователю\s*<@!?(\d{15,21})>", text, re.IGNORECASE)
        if m_id:
            return int(m_id.group(1))

        m_name = re.search(r"пользователю\s*@?([^.\n\r]+)", text, re.IGNORECASE)
        if m_name:
            target_name = m_name.group(1).strip().lstrip("@").lower()
            if target_name in self.name_to_id:
                return self.name_to_id[target_name]
        return None

    async def _handle_raw_message(self, msg_data: dict):
        ch_id = int(msg_data.get("channel_id", 0))
        if ch_id != REPRIMAND_CHANNEL_ID:
            return

        embeds = msg_data.get("embeds") or []
        if not embeds:
            return

        msg_id = msg_data.get("id", "0")
        for embed in embeds:
            full_text = self._extract_raw_embed_text(embed)
            low_text = full_text.lower()

            is_issue = ("выдать выговор" in low_text) or ("выдали выговор" in low_text)
            is_remove = ("снять выговор" in low_text) or ("сняли выговор" in low_text)

            if not is_issue and not is_remove:
                continue

            target_id = await self._resolve_target_user_from_reprimand(full_text)
            if not target_id:
                continue

            event_key = f"reprimand_{msg_id}_{'add' if is_issue else 'rem'}_{target_id}"
            if not await mark_event_processed(event_key):
                return

            if is_issue:
                exact_match = re.search(r"Теперь у него\s*(\d+)\s*выговор", full_text, re.IGNORECASE)
                exact_val = int(exact_match.group(1)) if exact_match else None
                new_warns = await change_warns(target_id, delta=1, exact=exact_val)

                reason = "Не указана"
                for f in embed.get("fields", []):
                    if "причина" in str(f.get("name", "")).lower():
                        reason = str(f.get("value", "")).strip()
                        break

                print(f"[Warns] Выдан выговор саппорту {target_id}. Теперь: {new_warns}/{MAX_WARNS}")
                if self.main_bot:
                    await send_log(
                        self.main_bot, "warns",
                        f"⚠️ Авто-фиксация: Саппорт <@{target_id}> получил выговор (Причина: `{reason}`). Теперь у него **`{new_warns}/{MAX_WARNS}`** выговоров."
                    )
            elif is_remove:
                new_warns = await change_warns(target_id, delta=-1)
                print(f"[Warns] Снят выговор у саппорта {target_id}. Теперь: {new_warns}/{MAX_WARNS}")
                if self.main_bot:
                    await send_log(
                        self.main_bot, "warns",
                        f"✅ Авто-фиксация: У саппорта <@{target_id}> снят выговор. Теперь у него **`{new_warns}/{MAX_WARNS}`** выговоров."
                    )

    async def _resolve_user_id_from_text(self, text: str) -> int | None:
        m = re.search(r"<@!?(\d{15,21})>", text)
        if m:
            return int(m.group(1))

        names_to_try = []
        at_match = re.search(r"@([^\s|]+)", text)
        if at_match:
            names_to_try.append(at_match.group(1).strip())
        pipe_match = re.search(r"\|\s*([^\s#\n]+)", text)
        if pipe_match:
            names_to_try.append(pipe_match.group(1).strip())

        for name in names_to_try:
            name_low = name.lower()
            if name_low in self.name_to_id:
                return self.name_to_id[name_low]

            try:
                url = (f"https://discord.com/api/v10/guilds/{MAIN_GUILD_ID}/members/search?query={name}&limit=5")
                async with self.session.get(url, headers=self._headers()) as resp:
                    if resp.status == 200:
                        for m in await resp.json():
                            self._cache_member_payload(m)
                            u = m.get("user", {})
                            if u.get("id"):
                                return int(u["id"])
            except Exception:
                pass
        return None

    async def _handle_ticket_message(self, msg_data: dict):
        ch_id = int(msg_data.get("channel_id", 0))
        if ch_id != TICKETS_CHANNEL_ID:
            return

        embeds = msg_data.get("embeds") or []
        if not embeds:
            return

        msg_id = msg_data.get("id", "0")
        for embed in embeds:
            full_text = self._extract_raw_embed_text(embed)
            if "Тикет был закрыт" not in full_text:
                continue

            ticket_id_match = re.search(r"ID тикета[:\s]*\n?\s*(\d+)", full_text, re.IGNORECASE)
            ticket_key = f"ticket_{ticket_id_match.group(1)}" if ticket_id_match else f"ticket_msg_{msg_id}"

            accepted_section = ""
            for f in embed.get("fields", []):
                if "Тикет принял" in str(f.get("name", "")):
                    accepted_section = str(f.get("value", ""))
                    break
            if not accepted_section:
                m_sec = re.search(r"Тикет принял[:\s]*\n?(.+)", full_text, re.IGNORECASE)
                if m_sec:
                    accepted_section = m_sec.group(1)
            if not accepted_section:
                continue

            support_id = await self._resolve_user_id_from_text(accepted_section)
            if not support_id:
                continue

            if not await mark_event_processed(ticket_key):
                return

            new_tickets = await increment_stat(support_id, "tickets", 1)
            print(f"[Tickets] Закрытый тикет {ticket_key} засчитан саппорту {support_id} (всего: {new_tickets})")

    async def _handle_gateway_dispatch(self, event_type: str, data: dict):
        if event_type == "READY":
            print("[+] Монитор успешно подключен к шлюзу Discord (READY)")
            guilds = data.get("guilds") or []
            for g in guilds:
                if int(g.get("id", 0)) == MAIN_GUILD_ID:
                    print(f"[+] Найден основной сервер {MAIN_GUILD_ID} в списке гильдий")
                    for vs in g.get("voice_states", []):
                        uid = int(vs.get("user_id", 0))
                        cid = vs.get("channel_id")
                        if uid and cid:
                            self.voice_states[uid] = int(cid)

        elif event_type == "GUILD_CREATE":
            if int(data.get("id", 0)) == MAIN_GUILD_ID:
                for m in data.get("members", []):
                    self._cache_member_payload(m)
                for vs in data.get("voice_states", []):
                    uid = int(vs.get("user_id", 0))
                    cid = vs.get("channel_id")
                    if uid and cid:
                        self.voice_states[uid] = int(cid)
                print(f"[+] Синхронизирован сервер {MAIN_GUILD_ID} (в голосовых: {len(self.voice_states)} чел.)")

        elif event_type == "VOICE_STATE_UPDATE":
            guild_id = int(data.get("guild_id") or 0)
            if guild_id and guild_id != MAIN_GUILD_ID:
                return
            uid = int(data.get("user_id", 0))
            cid = data.get("channel_id")
            if data.get("member"):
                self._cache_member_payload(data["member"])
            if cid:
                self.voice_states[uid] = int(cid)
            else:
                self.voice_states.pop(uid, None)

        elif event_type in ("GUILD_MEMBER_UPDATE", "GUILD_MEMBER_ADD"):
            if int(data.get("guild_id", 0)) == MAIN_GUILD_ID:
                self._cache_member_payload(data)

        elif event_type in ("MESSAGE_CREATE", "MESSAGE_UPDATE"):
            await self._handle_raw_message(data)
            await self._handle_ticket_message(data)

    async def _gateway_loop(self):
        gateway_url = "wss://gateway.discord.gg/?v10&encoding=json"
        
        # Интенты для бота: GUILDS (1) + GUILD_MEMBERS (2) + GUILD_VOICE_STATES (128) + 
        # GUILD_MESSAGES (512) + MESSAGE_CONTENT (32768) + GUILD_PRESENCES (256)
        bot_intents = 1 | 2 | 128 | 512 | 32768 | 256 

        while not self._closed:
            try:
                async with self.session.ws_connect(gateway_url, max_msg_size=0) as ws:
                    self.ws = ws
                    hello = await ws.receive_json()
                    hb_interval = hello.get("d", {}).get("heartbeat_interval", 41250) / 1000.0

                    identify_payload = {
                        "op": 2,
                        "d": {
                            "token": self.token,
                            "intents": bot_intents,
                            "properties": {
                                "os": "linux",
                                "browser": "monitor_bot",
                                "device": "monitor_bot"
                            },
                            "presence": {
                                "status": "online",
                                "since": 0,
                                "activities": [{"name": "Мониторинг сервера", "type": 4, "state": "Сбор статистики"}],
                                "afk": False
                            }
                        }
                    }
                    await ws.send_json(identify_payload)

                    self.seq = None

                    async def heartbeat_sender():
                        while not ws.closed and not self._closed:
                            await asyncio.sleep(hb_interval)
                            if not ws.closed:
                                await ws.send_json({"op": 1, "d": self.seq})

                    hb_task = asyncio.create_task(heartbeat_sender())
                    try:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                payload = json.loads(msg.data)
                                op = payload.get("op")
                                if payload.get("s") is not None:
                                    self.seq = payload["s"]
                                
                                if op == 0:
                                    await self._handle_gateway_dispatch(payload.get("t", ""), payload.get("d") or {})
                                elif op in (7, 9):
                                    print(f"[Monitor Gateway] Получен код {op}, переподключение...")
                                    break
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                    finally:
                        hb_task.cancel()
            except Exception as e:
                print(f"[Monitor Gateway] Переподключение через 5 сек (Ошибка: {e})...")
            await asyncio.sleep(5)

    async def start(self, token: str):
        await init_db()
        self.token = (token or "").strip().strip('"').strip("'")
        if not self.token:
            print("⚠️ [МОНИТОР] MONITOR_TOKEN пуст, мониторинг отключён.")
            return

        self.session = aiohttp.ClientSession()
        ok = await self._detect_token_mode()
        if not ok:
            await self.session.close()
            return

        print("[+] Запуск фоновых задач монитора...")
        await asyncio.gather(
            self._gateway_loop(),
            self._voice_minute_loop(),
            self._poll_channels_loop(),
        )

    async def close(self):
        self._closed = True
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session and not self.session.closed:
            await self.session.close()


async def run_standalone():
    mon = MonitorBot()
    await mon.start(MONITOR_TOKEN)

if __name__ == "__main__":
    asyncio.run(run_standalone())
