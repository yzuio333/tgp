"""Телеграм-бот: аккаунт парсит маркет, бот присылает карточки лотов.

Два клиента в одном процессе:
  * user  — ваш аккаунт (и пул доп. аккаунтов), доступ к payments.getResaleStarGifts;
  * bot   — обычный бот от @BotFather, шлёт сообщения, карточки и обрабатывает меню.

Разграничение прав:
  * CEO (ID: 7863407516): полный доступ, админ-панель, перезапуск, аккаунты, подписки;
  * Подписчики: доступ к полному мониторингу и фильтрам в ЛС;
  * Гости: экран-визитка с кнопками и переходом в ЛС поддержки @sahil_ui.
"""
import asyncio
import html
import os
import sys
import time

from telethon import Button, TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    MessageNotModifiedError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.tl import functions

from .. import config
from . import bot_ui, categories, memory, scanner
from . import owner as owner_mod
from .models import Listing, parse, passes

MAX_PER_CYCLE = 10000
SEND_PAUSE = 0.15
GROUP_SEND_ATTEMPTS = 3
GROUP_SEND_RETRY_DELAY = 1.0

HELP = f"""{bot_ui.E_SAT} <b>Gift Radar</b> — слежу за резейл-маркетом подарков.

<b>Панель</b>
/menu — живая панель: прогресс круга, статистика, все настройки.
Она обновляется сама и закрепляется в чате. Кнопки внизу экрана дублируют её разделы.

<b>Команды</b>
/start — подписаться на лоты
/stop — отписаться
/status — краткая сводка текстом
/find pepe — поиск по коллекциям, /find без слова сбрасывает
/set круг 30 — точное значение параметра (круг, пауза, лимит, от, до, подарки, нфт)

<b>Для CEO / Администратора:</b>
/admin — панель управления CEO
/sub <id> [дней] — выдать подписку пользователю
/unsub <id> — отозвать подписку
/setup_group — привязать текущую супергруппу
/bind <ключ> [topic_id] — привязать топик форума к категории

Под каждым лотом: <b>Открыть</b> — страница подарка, <b>Написать</b> — чат с продавцом, <b>✓ Готово</b> — убрать сообщение."""

KB_ACTIONS = {
    bot_ui.KB_RUN: "toggle",
    bot_ui.KB_PAUSE: "toggle",
    bot_ui.KB_PANEL: "panel",
    bot_ui.KB_COLS: "cols",
    bot_ui.KB_PARAMS: "params",
    bot_ui.KB_OWNER: "owner",
    bot_ui.KB_ADMIN: "admin",
}

SET_FIELDS = {
    "круг": ("poll_interval", 1, 3600, int),
    "пауза": ("request_delay", 0.0, 10.0, float),
    "лимит": ("page_limit", 10, 100, int),
    "от": ("min_price", 0, 100_000_000, int),
    "до": ("max_price", 0, 100_000_000, int),
    "подарки": ("max_owner_gifts", 0, 10_000, int),
    "нфт": ("max_owner_nft", 0, 10_000, int),
}


def render(item, owner_info=None) -> str:
    """HTML-текст сообщения о лоте."""
    esc = html.escape
    head = f'<a href="{item.url}">⁠</a>' if item.url else ""
    lines = [f"{head}{bot_ui.E_GIFT} <b>{esc(item.title)}</b> <code>#{item.num}</code>",
             f"<b>{esc(item.price_text)}</b>"]

    attrs = []
    if item.model:
        attrs.append(f"{bot_ui.E_PUZZLE} {esc(item.model)} · {item.model_rarity / 10:.1f}%")
    if item.backdrop:
        attrs.append(f"{bot_ui.E_ART} {esc(item.backdrop)} · {item.backdrop_rarity / 10:.1f}%")
    if item.symbol:
        attrs.append(f"✦ {esc(item.symbol)} · {item.symbol_rarity / 10:.1f}%")
    if attrs:
        lines.append("\n".join(attrs))

    if item.owner_username:
        seller = f'{bot_ui.E_USER} <a href="{item.owner_link}">@{esc(item.owner_username)}</a>'
        if item.owner:
            seller += f" — {esc(item.owner)}"
    elif item.owner:
        seller = f"{bot_ui.E_USER} {esc(item.owner)} <i>(без юзернейма)</i>"
    else:
        seller = f"{bot_ui.E_USER} <i>продавец скрыт</i>"
    lines.append(seller)

    if owner_info is not None and getattr(owner_info, "known", False):
        total = int(getattr(owner_info, "plain", 0) or 0) + int(getattr(owner_info, "nft", 0) or 0)
        nft = int(getattr(owner_info, "nft", 0) or 0)
        lines.append(f"{bot_ui.E_GIFT} Профиль: ⭐ подарков <b>{total}</b> · NFT <b>{nft}</b>")

    tail = []
    if item.supply_text:
        tail.append(f"тираж {item.supply_text}")
    if item.tags:
        tail.append(", ".join(esc(t) for t in item.tags))
    if tail:
        lines.append("<i>" + "  ·  ".join(tail) + "</i>")

    return "\n".join(lines)


def buttons(item) -> list:
    row = []
    if item.url:
        row.append(Button.url("Открыть", item.url))
    if item.owner_link:
        row.append(Button.url("Написать", item.owner_link))
    row.append(Button.inline("✓ Готово", b"done"))
    return [row]


def work_button() -> list:
    """Кнопка первичного забора лота из групповой ленты."""
    return [[Button.inline("! WORK", b"work", style="success")]]


class GiftBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.user: TelegramClient | None = None
        self.bot: TelegramClient | None = None
        self.sender: TelegramClient | None = None
        self.scanner_clients: list[TelegramClient] = []
        self._client_idx = 0
        self._admin_state: dict[int, dict] = {}

        self.seen = memory.SeenStore(config.data_dir() / "seen_bot.json")
        self.primed = False
        self.catalog: list[dict] = []
        self.targets: list[tuple[int, str]] = []
        self.scanning = True
        self.alive = True
        self._queries: dict[int, str] = {}
        self.owners = owner_mod.OwnerCache()

        self._hud_msg: dict[int, object] = {}
        self._hud_screen: dict[int, str] = {}
        self._hud_at = 0.0
        self._background_tasks: set[asyncio.Task] = set()
        self._shutdown_started = False
        self._restart_task: asyncio.Task | None = None
        self._restart_requested = False
        self._group_warning = ""
        self._group_lots: dict[tuple[int, int], tuple[Listing, object, object]] = {}
        self.stats = {
            "started": time.time(), "scanning": True, "cycles": 0,
            "found": 0, "sent": 0, "skip_owner": 0, "skip_filter": 0,
            "cycle_i": 0, "cycle_n": 0, "current": "", "last_found": 0.0,
            "targets": 0,
            "skip_by": {},
        }

    # ---------------- права и роли ----------------

    def is_ceo(self, user_id: int) -> bool:
        return int(user_id) == int(self.cfg.get("ceo_id", config.CEO_ID))

    def has_access(self, user_id: int) -> bool:
        if self.is_ceo(user_id):
            return True
        subs = self.cfg.get("subscriptions", {})
        sub = subs.get(str(user_id))
        if not sub:
            return False
        exp = sub.get("expires_at")
        if exp is None:
            return True
        return time.time() < float(exp)

    # ---------------- подписчики ----------------

    @property
    def subs(self) -> list[int]:
        return list(self.cfg.get("subscribers") or [])

    def add_sub(self, chat_id: int) -> bool:
        subs = self.subs
        if chat_id in subs:
            return False
        subs.append(chat_id)
        self.cfg["subscribers"] = subs
        config.save(self.cfg)
        return True

    def drop_sub(self, chat_id: int) -> bool:
        subs = self.subs
        if chat_id not in subs:
            return False
        subs.remove(chat_id)
        self.cfg["subscribers"] = subs
        config.save(self.cfg)
        return True

    # ---------------- запуск ----------------

    async def run(self) -> None:
        api_id, api_hash = int(self.cfg["api_id"]), self.cfg["api_hash"]

        self.user = TelegramClient(
            str(config.data_dir() / "session_bot_user"), api_id, api_hash,
            device_model="TG Gift Radar Bot", system_version="Windows 10",
            app_version="1.0",
        )
        self.log("Вхожу в аккаунт (нужен для чтения маркета)...")
        await self.user.start()
        me = await self.user.get_me()
        self.log(f"Аккаунт: {me.first_name or me.username or me.id}")

        self.bot = TelegramClient(
            str(config.data_dir() / "session_bot"), api_id, api_hash,
        )
        await self.bot.start(bot_token=self.cfg["bot_token"])
        bot_me = await self.bot.get_me()
        self.log(f"Бот: @{bot_me.username}")

        # Рассылка и управление ВСЕГДА идут через бота (защита личного аккаунта)
        self.sender = self.bot

        # Инициализируем пул сканеров: основной + дополнительные
        self.scanner_clients = [self.user]
        for acc in list(self.cfg.get("accounts", [])):
            try:
                acc_client = TelegramClient(
                    str(config.data_dir() / acc["session_name"]), api_id, api_hash,
                    device_model="TG Gift Radar Bot", system_version="Windows 10",
                    app_version="1.0",
                )
                await acc_client.connect()
                if await acc_client.is_user_authorized():
                    self.scanner_clients.append(acc_client)
                    self.log(f"✓ Доп. аккаунт подключен: {acc.get('name')} ({acc.get('phone')})")
                else:
                    self.log(f"Доп. аккаунт не авторизован: {acc.get('phone')}")
            except Exception as e:
                self.log(f"Ошибка подключения доп. аккаунта {acc.get('phone')}: {e}")

        self.log(f"Всего аккаунтов в пуле сканирования: {len(self.scanner_clients)}")

        known = self.seen.load()
        if known:
            self.primed = True
            self.log(f"Помню {known} лотов с прошлых запусков — повторов не будет")

        self._wire_handlers()
        await self.owners.load_me(self.user)
        self.catalog = await scanner.catalog(self.user)
        self._apply_targets()
        await self._auto_configure_group()

        for chat_id in self.subs:
            if self.has_access(chat_id):
                await self._safe_send(chat_id, f"{bot_ui.E_ROCKET} Бот перезапущен. /menu — панель управления.")

        self._background_tasks = {
            asyncio.create_task(self._scan_loop(), name="giftbot-scan"),
            asyncio.create_task(self._hud_loop(), name="giftbot-hud"),
        }
        self.log("Готово. Напишите боту /start, затем /menu. Ctrl+C — выход.")
        try:
            await self.bot.run_until_disconnected()
        except asyncio.CancelledError:
            pass
        finally:
            self.log("Остановка, отправка уведомлений...")
            await self.shutdown_message()
            if self._restart_requested:
                # Перезапуск выполняется из основного жизненного цикла, а не
                # из фоновой callback-задачи. Иначе loop закрывается раньше,
                # чем фоновая задача успевает вызвать os.execv().
                await asyncio.sleep(0.5)
                python = sys.executable
                os.execv(python, [python] + sys.argv)

    async def shutdown_message(self) -> None:
        """Отправляет подписчикам уведомление о выключении бота."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self.alive = False
        self.scanning = False
        self.stats["scanning"] = False

        # Не оставляем _scan_loop и _hud_loop жить до закрытия event loop.
        # Иначе asyncio при перезапуске пишет "Task was destroyed...".
        current = asyncio.current_task()
        pending = [task for task in self._background_tasks
                   if task is not current and not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._background_tasks.clear()

        if self.bot and self.bot.is_connected():
            for chat_id in self.subs:
                try:
                    await self.bot.send_message(chat_id, "⏹ Бот выключен, ожидайте перезапуска.")
                except Exception:
                    pass
            await self.bot.disconnect()

        for client in self.scanner_clients:
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                pass

        if self.user and self.user.is_connected() and self.user not in self.scanner_clients:
            await self.user.disconnect()

    async def _auto_bind_group_topics(self, group_id: int) -> tuple[dict, str | None]:
        """Находит уже созданные форумные топики и привязывает их по названиям."""
        # Bot API/MTProto ограничивает GetForumTopicsRequest для bot-клиентов.
        # Читаем список тем пользовательским аккаунтом, а сообщения всё равно
        # отправляем отдельно через self.bot.
        reader = self.user or self.bot
        try:
            result = await asyncio.wait_for(
                reader(functions.messages.GetForumTopicsRequest(
                    peer=int(group_id),
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                    q="",
                )),
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Не удалось прочитать топики группы {group_id}: {exc}")
            return {}, exc.__class__.__name__

        group = self.cfg.setdefault("group_settings", {})
        topics = group.setdefault("topics", {})
        bound = {}
        for topic in getattr(result, "topics", []) or []:
            key = categories.topic_key(getattr(topic, "title", ""))
            if key and not topics.get(key):
                topics[key] = int(topic.id)
                bound[key] = int(topic.id)

        self._save()
        return bound, None

    async def _find_forum_groups(self) -> list[tuple[int, str]]:
        """Возвращает доступные аккаунту чтения форумные супергруппы."""
        found = []
        reader = self.user or self.bot
        try:
            async for dialog in reader.iter_dialogs():
                entity = dialog.entity
                if not getattr(entity, "megagroup", False):
                    continue
                if not getattr(entity, "forum", False):
                    continue
                found.append((int(dialog.id), getattr(entity, "title", str(dialog.id))))
        except Exception as exc:  # noqa: BLE001
            self.log(f"Не удалось найти форумные группы: {exc}")
        return found

    async def _auto_configure_group(self) -> tuple[int | None, list[tuple[int, str]]]:
        """Автоматически подключает единственную форумную группу, если она есть."""
        group = self.cfg.setdefault("group_settings", {})
        current_id = group.get("group_id")
        if current_id:
            return int(current_id), []

        candidates = await self._find_forum_groups()
        if len(candidates) != 1:
            return None, candidates

        group_id, title = candidates[0]
        group["group_id"] = group_id
        bound, error = await self._auto_bind_group_topics(group_id)
        self._save()
        if error:
            self.log(f"Группа найдена: {title} ({group_id}), но топики не прочитаны")
        else:
            self.log(f"Группа найдена: {title} ({group_id}), привязано топиков: {len(bound)}")
        return group_id, candidates

    def _apply_targets(self) -> None:
        chosen = set(self.cfg.get("collections") or [])
        excluded = [str(value).casefold().strip()
                    for value in self.cfg.get("excluded_collections", []) if str(value).strip()]

        def allowed(collection: dict) -> bool:
            title = str(collection.get("title", "")).casefold()
            return not any(value in title for value in excluded)

        if self.cfg.get("collections_set"):
            self.targets = [(c["id"], c["title"]) for c in self.catalog
                            if c["id"] in chosen and allowed(c)]
        else:
            self.targets = [(c["id"], c["title"]) for c in self.catalog
                            if c["resale"] and allowed(c)]
        if excluded:
            self.log("Исключены коллекции: " + ", ".join(excluded))
        self.log(f"Отслеживаю коллекций: {len(self.targets)}")

    def _save(self) -> None:
        config.save(self.cfg)

    # ---------------- команды и кнопки ----------------

    def _wire_handlers(self) -> None:
        bot = self.bot

        @bot.on(events.NewMessage(pattern=r"^/start"))
        async def _(event):
            user_id = event.sender_id or event.chat_id
            if not self.has_access(user_id):
                text, btns = bot_ui.guest_welcome()
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
                return

            added = self.add_sub(event.chat_id)
            is_ceo = self.is_ceo(user_id)
            msg = "👑 <b>Добро пожаловать, CEO!</b>" if is_ceo else ("✅ Подписка активна, лоты пойдут сюда." if added else "Подписка активна.")
            await self.bot.send_message(
                event.chat_id,
                msg,
                parse_mode="html",
                buttons=bot_ui.keyboard(self.scanning, is_ceo=is_ceo))
            await self._send_menu(event.chat_id)
            if added:
                self.log(f"Новый подписчик: {event.chat_id}")

        @bot.on(events.NewMessage(func=lambda e: e.raw_text in KB_ACTIONS))
        async def _(event):
            """Нажатия на нижнюю клавиатуру."""
            user_id = event.sender_id or event.chat_id
            if not self.has_access(user_id):
                text, btns = bot_ui.guest_welcome()
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
                return

            action = KB_ACTIONS[event.raw_text]
            is_ceo = self.is_ceo(user_id)

            if action == "admin":
                if not is_ceo:
                    await self.bot.send_message(event.chat_id, "❌ Доступ только для CEO.")
                    return
                text, btns = bot_ui.admin_menu(self.cfg)
                self._hud_screen[event.chat_id] = "admin"
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
                return

            if action == "toggle":
                self.scanning = not self.scanning
                self.stats["scanning"] = self.scanning
                await self.bot.send_message(
                    event.chat_id,
                    f"{bot_ui.E_GREEN} Слежу за маркетом." if self.scanning else f"{bot_ui.E_PAUSE} Поставил на паузу.",
                    parse_mode="html",
                    buttons=bot_ui.keyboard(self.scanning, is_ceo=is_ceo))
                await self._send_menu(event.chat_id)
            elif action == "panel":
                await self._send_menu(event.chat_id)
            elif action == "cols":
                text, btns = bot_ui.collections_page(
                    self.catalog, self._chosen(), 0, self._queries.get(event.chat_id, ""))
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
            elif action == "params":
                text, btns = bot_ui.params_menu(self.cfg)
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
            elif action == "owner":
                text, btns = bot_ui.owner_menu(self.cfg)
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/admin"))
        async def _(event):
            user_id = event.sender_id or event.chat_id
            if not self.is_ceo(user_id):
                await event.respond("❌ Доступ только для CEO.")
                return
            self._hud_screen[event.chat_id] = "admin"
            text, btns = bot_ui.admin_menu(self.cfg)
            await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/sub(?:\s+(\d+))?(?:\s+(\d+))?"))
        async def _(event):
            if not self.is_ceo(event.sender_id or event.chat_id):
                return
            uid = event.pattern_match.group(1)
            if not uid:
                await event.respond("Формат: <code>/sub &lt;user_id&gt; [дней]</code>", parse_mode="html")
                return
            days_str = event.pattern_match.group(2)
            if days_str:
                days = int(days_str)
                exp = time.time() + days * 86400
                desc = f"на {days} дней"
            else:
                exp = None
                desc = "бессрочно"

            if "subscriptions" not in self.cfg:
                self.cfg["subscriptions"] = {}
            self.cfg["subscriptions"][str(uid)] = {"expires_at": exp, "role": "sub"}
            self._save()
            await event.respond(f"✅ Подписка пользователю <code>{uid}</code> выдана ({desc}).", parse_mode="html")
            try:
                await self.bot.send_message(int(uid), f"🎉 <b>Вам выдана подписка ({desc})!</b>\nНапишите /menu для доступа к парсеру.", parse_mode="html")
            except Exception:
                pass

        @bot.on(events.NewMessage(pattern=r"^/unsub(?:\s+(\d+))?"))
        async def _(event):
            if not self.is_ceo(event.sender_id or event.chat_id):
                return
            uid = event.pattern_match.group(1)
            if not uid:
                await event.respond("Формат: <code>/unsub &lt;user_id&gt;</code>", parse_mode="html")
                return
            if str(uid) == str(self.cfg.get("ceo_id", config.CEO_ID)):
                await event.respond("❌ Нельзя отозвать подписку у CEO.")
                return
            subs = self.cfg.get("subscriptions", {})
            if str(uid) in subs:
                del subs[str(uid)]
                self._save()
                await event.respond(f"✅ Подписка у пользователя <code>{uid}</code> отозвана.", parse_mode="html")
            else:
                await event.respond(f"Пользователь <code>{uid}</code> не найден в подписчиках.", parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/(?:setup_group|set_group)"))
        async def _(event):
            if not self.is_ceo(event.sender_id or event.chat_id):
                return
            if event.is_private:
                await event.respond("⚠️ Эту команду нужно отправлять внутри супергруппы, куда вы добавили бота.")
                return

            if "group_settings" not in self.cfg:
                self.cfg["group_settings"] = {"enabled": True, "group_id": None, "topics": {}}
            previous_group_id = self.cfg["group_settings"].get("group_id")
            self.cfg["group_settings"]["group_id"] = event.chat_id
            if previous_group_id != event.chat_id:
                self.cfg["group_settings"]["topics"] = {}
            self._save()

            bound, bind_error = await self._auto_bind_group_topics(event.chat_id)
            keys_list = "\n".join(f"• <code>{k}</code> — {v}" for k, v in categories.CATEGORIES.items())
            if bound:
                bound_text = "\n".join(
                    f"• {categories.CATEGORIES[key]} → топик #{topic_id}"
                    for key, topic_id in bound.items()
                )
                bind_status = f"\n\n<b>Автоматически привязано:</b>\n{bound_text}"
            elif bind_error:
                bind_status = (
                    "\n\n⚠️ Не удалось прочитать список топиков. "
                    "Привяжите их вручную командой <code>/bind ключ</code> "
                    "внутри нужной темы."
                )
            else:
                bind_status = (
                    "\n\n⚠️ Совпадений по названиям не найдено. "
                    "Привяжите темы вручную командой <code>/bind ключ</code>."
                )
            await event.respond(
                f"✅ <b>Супергруппа привязана (ID: <code>{event.chat_id}</code>)!</b>\n\n"
                "Бот попытался сопоставить уже созданные темы по названиям."
                f"{bind_status}\n\n"
                "Если какая-то тема не совпала, отправьте в ней команду "
                "<code>/bind &lt;ключ&gt;</code>.\n\n"
                f"<b>Доступные ключи:</b>\n{keys_list}",
                parse_mode="html"
            )

        @bot.on(events.NewMessage(pattern=r"^/bind(?:\s+(\S+))?(?:\s+(\d+))?"))
        async def _(event):
            if not self.is_ceo(event.sender_id or event.chat_id):
                return
            if event.is_private:
                await event.respond("⚠️ Команду /bind нужно отправлять внутри нужной темы форумной группы.")
                return
            key = (event.pattern_match.group(1) or "").lower()
            explicit_topic = event.pattern_match.group(2)

            if not key or key not in categories.CATEGORIES:
                keys = ", ".join(f"<code>{k}</code>" for k in categories.CATEGORIES)
                await event.respond(f"Формат: <code>/bind &lt;ключ&gt; [topic_id]</code>\nДоступные ключи: {keys}", parse_mode="html")
                return

            topic_id = None
            if explicit_topic:
                topic_id = int(explicit_topic)
            elif event.reply_to:
                topic_id = getattr(event.reply_to, "reply_to_top_id", None) or getattr(event.reply_to, "reply_to_msg_id", None)
            elif event.reply_to_msg_id:
                topic_id = event.reply_to_msg_id

            if not topic_id:
                await event.respond("⚠️ Не удалось определить ID топика. Отправьте команду внутри темы форума (или ответом на сообщение), либо укажите ID явно: <code>/bind &lt;ключ&gt; &lt;topic_id&gt;</code>", parse_mode="html")
                return

            if "group_settings" not in self.cfg:
                self.cfg["group_settings"] = {"enabled": True, "group_id": None, "topics": {}}
            previous_group_id = self.cfg["group_settings"].get("group_id")
            self.cfg["group_settings"]["group_id"] = event.chat_id
            if previous_group_id != event.chat_id:
                self.cfg["group_settings"]["topics"] = {}
            if "topics" not in self.cfg["group_settings"]:
                self.cfg["group_settings"]["topics"] = {}

            self.cfg["group_settings"]["topics"][key] = int(topic_id)
            self._save()
            title = categories.CATEGORIES[key]
            await event.respond(f"✅ Категория <b>{title}</b> привязана к топику #{topic_id}!", parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/stop"))
        async def _(event):
            dropped = self.drop_sub(event.chat_id)
            await self.bot.send_message(event.chat_id, "⏹ Отписал." if dropped else "Вы и не были подписаны.")

        @bot.on(events.NewMessage(pattern=r"^/help"))
        async def _(event):
            await self.bot.send_message(event.chat_id, HELP, parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/menu"))
        async def _(event):
            user_id = event.sender_id or event.chat_id
            if not self.has_access(user_id):
                text, btns = bot_ui.guest_welcome()
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
                return
            await self._send_menu(event.chat_id)

        @bot.on(events.NewMessage(pattern=r"^/test"))
        async def _(event):
            demo = Listing(
                gift_id=0, num=1234, title="Пример подарка", slug="",
                price=12500, currency="stars", issued=800, total=1000,
                model="Classic", model_rarity=15, backdrop="Onyx Black",
                backdrop_rarity=80, symbol="Diamond", symbol_rarity=50,
                owner="Тестовый продавец", owner_username="durov",
                collection="Пример", ts=time.time(), tags=["тест"],
            )
            await self._safe_send(event.chat_id, render(demo), buttons(demo))
            await self.bot.send_message(
                event.chat_id,
                "☝️ Так выглядит сообщение о лоте.\n"
                f"Подписчиков: <b>{len(self.subs)}</b>, "
                f"коллекций: <b>{len(self.targets)}</b>, "
                f"первый круг пройден: <b>{'да' if self.primed else 'нет'}</b>.",
                parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/status"))
        async def _(event):
            names = ", ".join(t for _i, t in self.targets[:15])
            more = f" и ещё {len(self.targets) - 15}" if len(self.targets) > 15 else ""
            await self.bot.send_message(
                event.chat_id,
                f"Слежение: <b>{'идёт' if self.scanning else 'на паузе'}</b>\n"
                f"Коллекций: <b>{len(self.targets)}</b>\n{html.escape(names)}{more}\n\n"
                f"Подписчиков: {len(self.subs)}\nЗапомнено лотов: {len(self.seen)}",
                parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/find(?:\s+(.*))?$"))
        async def _(event):
            user_id = event.sender_id or event.chat_id
            if not self.has_access(user_id):
                text, btns = bot_ui.guest_welcome()
                await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")
                return
            query = (event.pattern_match.group(1) or "").strip()
            self._queries[event.chat_id] = query
            text, btns = bot_ui.collections_page(
                self.catalog, self._chosen(), 0, query)
            await self.bot.send_message(event.chat_id, text, buttons=btns, parse_mode="html")

        @bot.on(events.NewMessage(pattern=r"^/set(?:\s+(\S+))?(?:\s+(\S+))?"))
        async def _(event):
            user_id = event.sender_id or event.chat_id
            if not self.has_access(user_id):
                return
            field = (event.pattern_match.group(1) or "").lower()
            raw = event.pattern_match.group(2) or ""
            if field not in SET_FIELDS:
                await self.bot.send_message(
                    event.chat_id,
                    "Что менять: " + ", ".join(SET_FIELDS) + "\nНапример: /set круг 30")
                return
            key, lo, hi, cast = SET_FIELDS[field]
            try:
                value = cast(raw.replace(",", "."))
            except ValueError:
                await self.bot.send_message(event.chat_id, "Нужно число, например: /set круг 30")
                return
            value = max(lo, min(hi, value))
            self.cfg[key] = value
            self._save()
            await self.bot.send_message(event.chat_id, f"✅ {field} = {value}")

        # FSM-обработчик интерактивного добавления аккаунтов для CEO
        @bot.on(events.NewMessage)
        async def _fsm_handler(event):
            if not event.is_private:
                return
            chat_id = event.chat_id
            if chat_id not in self._admin_state:
                return
            text = (event.raw_text or "").strip()
            if text.startswith("/"):
                if text == "/cancel":
                    self._admin_state.pop(chat_id, None)
                    await event.respond("❌ Добавление аккаунта отменено.")
                return

            state_data = self._admin_state[chat_id]
            stage = state_data.get("stage")

            if stage == "phone":
                phone = text.replace(" ", "").replace("-", "")
                if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 10:
                    await event.respond("⚠️ Некорректный номер. Введите в формате <code>+79123456789</code> или <code>/cancel</code>:", parse_mode="html")
                    return
                clean_phone = phone.replace("+", "")
                session_name = f"session_user_{clean_phone}"
                api_id, api_hash = int(self.cfg["api_id"]), self.cfg["api_hash"]
                new_client = TelegramClient(
                    str(config.data_dir() / session_name), api_id, api_hash,
                    device_model="TG Gift Radar Bot", system_version="Windows 10", app_version="1.0"
                )
                await new_client.connect()
                try:
                    sent = await new_client.send_code_request(phone)
                    self._admin_state[chat_id] = {
                        "stage": "code",
                        "phone": phone,
                        "session_name": session_name,
                        "client": new_client,
                        "phone_code_hash": sent.phone_code_hash,
                    }
                    await event.respond(f"📩 Код подтверждения отправлен на <b>{phone}</b>.\n\nВведите полученный код (можно с пробелами) или <code>/cancel</code>:", parse_mode="html")
                except Exception as e:
                    await new_client.disconnect()
                    self._admin_state.pop(chat_id, None)
                    await event.respond(f"❌ Ошибка отправки кода: {e}")

            elif stage == "code":
                code = text.replace(" ", "").replace("-", "")
                phone = state_data["phone"]
                phone_code_hash = state_data["phone_code_hash"]
                new_client = state_data["client"]
                try:
                    await new_client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                    me = await new_client.get_me()
                    acc_info = {
                        "phone": phone,
                        "session_name": state_data["session_name"],
                        "name": me.first_name or me.username or str(me.id),
                        "id": me.id,
                    }
                    if "accounts" not in self.cfg:
                        self.cfg["accounts"] = []
                    self.cfg["accounts"].append(acc_info)
                    self._save()
                    self.scanner_clients.append(new_client)
                    self._admin_state.pop(chat_id, None)
                    await event.respond(f"✅ Аккаунт <b>{html.escape(acc_info['name'])}</b> успешно подключен к парсеру!", parse_mode="html")
                except SessionPasswordNeededError:
                    state_data["stage"] = "2fa"
                    await event.respond("🔐 Включен облачный пароль (2FA).\n\nВведите пароль или <code>/cancel</code>:", parse_mode="html")
                except Exception as e:
                    await event.respond(f"⚠️ Ошибка кода: {e}.\nПопробуйте ещё раз или <code>/cancel</code>:")

            elif stage == "2fa":
                password = text
                new_client = state_data["client"]
                phone = state_data["phone"]
                try:
                    await new_client.sign_in(password=password)
                    me = await new_client.get_me()
                    acc_info = {
                        "phone": phone,
                        "session_name": state_data["session_name"],
                        "name": me.first_name or me.username or str(me.id),
                        "id": me.id,
                    }
                    if "accounts" not in self.cfg:
                        self.cfg["accounts"] = []
                    self.cfg["accounts"].append(acc_info)
                    self._save()
                    self.scanner_clients.append(new_client)
                    self._admin_state.pop(chat_id, None)
                    await event.respond(f"✅ Аккаунт <b>{html.escape(acc_info['name'])}</b> успешно авторизован с 2FA и подключен!", parse_mode="html")
                except Exception as e:
                    await event.respond(f"⚠️ Ошибка 2FA: {e}.\nПопробуйте ещё раз или <code>/cancel</code>:")

        @bot.on(events.CallbackQuery)
        async def _(event):
            await self._on_button(event)

    async def _on_button(self, event) -> None:
        data = event.data.decode()
        chat_id = event.chat_id
        user_id = event.sender_id or chat_id
        is_ceo = self.is_ceo(user_id)

        if data == "done":
            await event.delete()
            return
        if data == "work":
            await self._claim_group_lot(event)
            return
        if data == "noop":
            await event.answer()
            return

        # Кнопки для гостей
        if data.startswith("guest:"):
            await event.answer("В разработке...", alert=True)
            return

        # Проверка доступа к полному функционалу
        if not self.has_access(user_id):
            await event.answer("Доступ ограничен. Необходима подписка.", alert=True)
            return

        # Админ-действия
        if data.startswith("admin:"):
            if not is_ceo:
                await event.answer("Доступ только для CEO.", alert=True)
                return
            await self._on_admin_button(event, data)
            return

        note = None
        if data == "menu":
            pass
        elif data == "scan:toggle":
            self.scanning = not self.scanning
            note = "Слежу" if self.scanning else "Пауза"
        elif data.startswith("cur:"):
            key = "cur_stars" if data.endswith("stars") else "cur_ton"
            other = "cur_ton" if key == "cur_stars" else "cur_stars"
            if self.cfg.get(key, True) and not self.cfg.get(other, True):
                await event.answer("Нужна хотя бы одна валюта", alert=True)
                return
            self.cfg[key] = not self.cfg.get(key, True)
            self._save()
        elif data == "params":
            self._hud_screen[chat_id] = "params"
            await self._edit(event, *bot_ui.params_menu(self.cfg))
            return
        elif data == "owner":
            self._hud_screen[chat_id] = "owner"
            await self._edit(event, *bot_ui.owner_menu(self.cfg))
            return
        elif data in ("writable", "russian", "hidden", "username"):
            flag_map = {
                "writable": "only_writable",
                "russian": "only_russian",
                "hidden": "skip_hidden_owner",
                "username": "require_username",
            }
            k = flag_map[data]
            self.cfg[k] = not self.cfg.get(k, False)
            self._save()
            self._hud_screen[chat_id] = "owner"
            await self._edit(event, *bot_ui.owner_menu(self.cfg))
            return
        elif data == "owner:clear":
            self.cfg["max_owner_gifts"] = 0
            self.cfg["max_owner_nft"] = 0
            self.cfg["only_writable"] = False
            self.cfg["only_russian"] = False
            self.cfg["skip_hidden_owner"] = False
            self.cfg["require_username"] = False
            self._save()
            self._hud_screen[chat_id] = "owner"
            await self._edit(event, *bot_ui.owner_menu(self.cfg))
            await event.answer("Лимиты сброшены")
            return
        elif data == "existing":
            self.cfg["show_existing_on_start"] = not self.cfg.get("show_existing_on_start", False)
            self._save()
            self._hud_screen[chat_id] = "params"
            await self._edit(event, *bot_ui.params_menu(self.cfg))
            return
        elif data == "rich":
            self.cfg["show_rich"] = not self.cfg.get("show_rich", False)
            self._save()
            self._hud_screen[chat_id] = "params"
            await self._edit(event, *bot_ui.params_menu(self.cfg))
            return
        elif data == "reset":
            self.seen.clear()
            self.primed = False
            self.owners.forget()
            self._hud_screen[chat_id] = "params"
            await self._edit(event, *bot_ui.params_menu(self.cfg))
            await event.answer("Память очищена")
            return
        elif data.startswith("num:"):
            _p, field, delta = data.split(":")
            self._nudge(field, int(delta))
            screen = bot_ui.owner_menu if field in ("ogifts", "onft") else bot_ui.params_menu
            self._hud_screen[chat_id] = "owner" if field in ("ogifts", "onft") else "params"
            await self._edit(event, *screen(self.cfg))
            return
        elif data.startswith("col:"):
            self._toggle_collection(int(data.split(":")[1]))
            self._hud_screen[chat_id] = "cols"
            await self._show_collections(event, self._page_of(event))
            return
        elif data == "cols:all":
            self.cfg["collections"] = [c["id"] for c in self.catalog if c["resale"]]
            self.cfg["collections_set"] = True
            self._save()
            self._apply_targets()
            self._hud_screen[chat_id] = "cols"
            await self._show_collections(event, 0)
            return
        elif data == "cols:none":
            self.cfg["collections"] = []
            self.cfg["collections_set"] = True
            self._save()
            self._apply_targets()
            self._hud_screen[chat_id] = "cols"
            await self._show_collections(event, 0)
            return
        elif data.startswith("cols:"):
            self._hud_screen[chat_id] = "cols"
            await self._show_collections(event, int(data.split(":")[1]))
            return

        text, btns = bot_ui.hud(self.cfg, self._snapshot(), is_ceo=is_ceo)
        self._hud_screen[chat_id] = "menu"
        await self._edit(event, text, btns)
        await event.answer(note or "")

    async def _claim_group_lot(self, event) -> None:
        """Выдаёт лот первому нажавшему кнопку WORK."""
        key = (int(event.chat_id), int(event.message_id))
        record = self._group_lots.pop(key, None)
        if record is None:
            await event.answer("Лот уже забрали или он устарел.", alert=True)
            return

        item, owner_info, seller = record
        try:
            await event.delete()
        except RPCError as exc:
            self.log(f"Не удалось удалить забранный лот {item.key}: {exc.__class__.__name__}")

        if (seller is not None and self.user is not None
                and not getattr(owner_info, "counts_known", False)):
            try:
                owner_info = await self.owners.info(
                    self.user, seller, with_counts=True
                )
            except FloodWaitError as exc:
                self.log(f"FloodWait на профиле победителя: {exc.seconds} сек")
                await asyncio.sleep(exc.seconds + 1)
            except RPCError as exc:
                self.log(f"Не удалось получить профиль победителя: {exc.__class__.__name__}")

        text = render(item, owner_info)
        try:
            await self.bot.send_message(
                event.sender_id,
                text,
                buttons=buttons(item),
                parse_mode="html",
                link_preview=True,
            )
            await event.answer("Лот отправлен вам в личные сообщения.")
        except RPCError as exc:
            self.log(f"Не удалось отправить лот {item.key} победителю {event.sender_id}: {exc}")
            await event.answer(
                "Лот забран, но Telegram не разрешил написать вам в личные сообщения.",
                alert=True,
            )

    async def _on_admin_button(self, event, data: str) -> None:
        chat_id = event.chat_id
        if data == "admin:menu":
            self._hud_screen[chat_id] = "admin"
            text, btns = bot_ui.admin_menu(self.cfg)
            await self._edit(event, text, btns)
            await event.answer()
            return

        elif data == "admin:toggle_group":
            grp = self.cfg.setdefault("group_settings", {})
            turning_on = not grp.get("enabled", True)
            if turning_on and not grp.get("group_id"):
                group_id, candidates = await self._auto_configure_group()
                if not group_id:
                    if len(candidates) > 1:
                        names = ", ".join(title for _gid, title in candidates[:5])
                        await event.answer(
                            f"Найдено несколько форумных групп: {names}. Отправьте /setup_group в нужной.",
                            alert=True,
                        )
                    else:
                        await event.answer(
                            "Сначала добавьте бота в форумную супергруппу и отправьте там /setup_group.",
                            alert=True,
                        )
                    return
                grp = self.cfg.setdefault("group_settings", {})
            if turning_on and not any(grp.get("topics", {}).values()):
                bound, error = await self._auto_bind_group_topics(grp["group_id"])
                if not any(grp.get("topics", {}).values()):
                    detail = "не удалось прочитать топики" if error else "не найдено ни одного привязанного топика"
                    await event.answer(f"Нельзя включить рассылку: {detail}.", alert=True)
                    return
            grp["enabled"] = turning_on
            self._save()
            text, btns = bot_ui.admin_menu(self.cfg)
            await self._edit(event, text, btns)
            await event.answer("Статус рассылки в группу изменён")
            return

        elif data == "admin:cats":
            self._hud_screen[chat_id] = "admin_cats"
            text, btns = bot_ui.admin_categories_menu(self.cfg)
            await self._edit(event, text, btns)
            await event.answer()
            return

        elif data.startswith("admin:cat:"):
            cat_key = data.split(":", 2)[2]
            disabled = self.cfg.setdefault("disabled_categories", [])
            if cat_key in disabled:
                disabled.remove(cat_key)
                status = "включена"
            else:
                disabled.append(cat_key)
                status = "отключена"
            self._save()
            text, btns = bot_ui.admin_categories_menu(self.cfg)
            await self._edit(event, text, btns)
            await event.answer(f"Категория {status}")
            return

        elif data == "admin:subs":
            self._hud_screen[chat_id] = "admin_subs"
            text, btns = bot_ui.admin_subs_menu(self.cfg)
            await self._edit(event, text, btns)
            await event.answer()
            return

        elif data == "admin:accs":
            self._hud_screen[chat_id] = "admin_accs"
            text, btns = bot_ui.admin_accounts_menu(self.cfg, len(self.scanner_clients))
            await self._edit(event, text, btns)
            await event.answer()
            return

        elif data == "admin:clear_accs":
            self.cfg["accounts"] = []
            self._save()
            self.scanner_clients = [self.user] if self.user else []
            text, btns = bot_ui.admin_accounts_menu(self.cfg, len(self.scanner_clients))
            await self._edit(event, text, btns)
            await event.answer("Дополнительные аккаунты очищены")
            return

        elif data == "admin:add_acc":
            self._admin_state[chat_id] = {"stage": "phone"}
            await event.answer()
            await self.bot.send_message(
                chat_id,
                "📱 <b>Добавление аккаунта парсера</b>\n\n"
                "Введите номер телефона в международном формате (например, <code>+79123456789</code>) или <code>/cancel</code> для отмены:",
                parse_mode="html"
            )
            return

        elif data == "admin:restart":
            await event.answer("Перезапуск бота...")
            await self._restart_bot(chat_id)
            return

    async def _restart_bot(self, chat_id: int) -> None:
        await self.bot.send_message(chat_id, "🔄 Перезапускаю бота...")
        # Нельзя отключать bot прямо из CallbackQuery-обработчика:
        # Telethon отменяет текущий handler во время disconnect(), и код
        # после await self.bot.disconnect() не выполняется. В итоге процесс
        # закрывает event loop с живыми сетевыми задачами.
        if self._restart_task and not self._restart_task.done():
            return
        self._restart_task = asyncio.create_task(
            self._restart_process(), name="giftbot-restart"
        )

    async def _restart_process(self) -> None:
        """Запрашивает перезапуск, оставляя завершение основному циклу."""
        try:
            await asyncio.sleep(0.5)
            self._restart_requested = True
            # Это только выводит run_until_disconnected() в его штатный
            # finally, где клиенты закрываются и затем запускается процесс.
            if self.bot and self.bot.is_connected():
                await self.bot.disconnect()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log(f"Ошибка перезапуска: {exc}")

    def _nudge(self, field: str, delta: int) -> None:
        if field == "interval":
            self.cfg["poll_interval"] = max(1, min(3600, int(self.cfg.get("poll_interval", 20)) + delta))
        elif field == "delay":
            value = float(self.cfg.get("request_delay", 0.6)) + delta / 10
            self.cfg["request_delay"] = round(max(0.0, min(10.0, value)), 1)
        elif field == "limit":
            self.cfg["page_limit"] = max(10, min(100, int(self.cfg.get("page_limit", 50)) + delta))
        elif field == "ogifts":
            self.cfg["max_owner_gifts"] = max(0, int(self.cfg.get("max_owner_gifts", 0) or 0) + delta)
        elif field == "onft":
            self.cfg["max_owner_nft"] = max(0, int(self.cfg.get("max_owner_nft", 0) or 0) + delta)
        self._save()

    def _toggle_collection(self, gift_id: int) -> None:
        chosen = set(self.cfg.get("collections") or [])
        if not self.cfg.get("collections_set"):
            chosen = {c["id"] for c in self.catalog if c["resale"]}
        chosen.symmetric_difference_update({gift_id})
        self.cfg["collections"] = sorted(chosen)
        self.cfg["collections_set"] = True
        self._save()
        self._apply_targets()

    def _chosen(self) -> set:
        if self.cfg.get("collections_set"):
            return set(self.cfg.get("collections") or [])
        return {c["id"] for c in self.catalog if c["resale"]}

    def _page_of(self, event) -> int:
        try:
            for row in event.original_update.message.reply_markup.rows:
                for b in row.buttons:
                    data = getattr(b, "data", b"") or b""
                    if data.startswith(b"cols:") and data[5:].isdigit():
                        return int(data[5:])
        except Exception:
            pass
        return 0

    async def _show_collections(self, event, page: int) -> None:
        query = self._queries.get(event.chat_id, "")
        text, btns = bot_ui.collections_page(
            self.catalog, self._chosen(), page, query)
        await self._edit(event, text, btns)
        await event.answer()

    def _snapshot(self) -> dict:
        st = dict(self.stats)
        st["scanning"] = self.scanning
        st["targets"] = len(self.targets)
        st["subs"] = len(self.subs)
        st["primed"] = self.primed
        return st

    async def _send_menu(self, chat_id: int) -> None:
        is_ceo = self.is_ceo(chat_id)
        text, btns = bot_ui.hud(self.cfg, self._snapshot(), is_ceo=is_ceo)
        try:
            msg = await self.bot.send_message(chat_id, text, parse_mode="html",
                                              buttons=btns, link_preview=False)
            self._hud_msg[chat_id] = msg
            self._hud_screen[chat_id] = "menu"
            try:
                await self.bot.pin_message(chat_id, msg, notify=False)
            except RPCError:
                pass
        except RPCError as e:
            self.log(f"Не отправить панель в {chat_id}: {e.__class__.__name__}")

    async def _hud_loop(self) -> None:
        while self.alive:
            await asyncio.sleep(10)
            try:
                await self._refresh_hud(force=True)
            except Exception as e:
                self.log(f"панель: {e.__class__.__name__}")

    async def _refresh_hud(self, force: bool = False) -> None:
        if not self._hud_msg:
            return
        if not force and time.time() - self._hud_at < 5:
            return
        self._hud_at = time.time()

        for chat_id, msg in list(self._hud_msg.items()):
            if self._hud_screen.get(chat_id, "menu") != "menu":
                continue
            is_ceo = self.is_ceo(chat_id)
            text, btns = bot_ui.hud(self.cfg, self._snapshot(), is_ceo=is_ceo)
            try:
                await self.bot.edit_message(msg, text, parse_mode="html", buttons=btns, link_preview=False)
            except MessageNotModifiedError:
                pass
            except RPCError:
                self._hud_msg.pop(chat_id, None)

    async def _edit(self, event, text: str, btns) -> None:
        try:
            await self.bot.edit_message(event.chat_id, event.message_id,
                                        text, parse_mode="html", buttons=btns,
                                        link_preview=False)
        except MessageNotModifiedError:
            pass
        except RPCError as e:
            self.log(f"Не изменить меню: {e.__class__.__name__}")

    # ---------------- цикл сканирования ----------------

    async def _scan_loop(self) -> None:
        while self.alive:
            if not self.scanning or not self.targets:
                await asyncio.sleep(1)
                continue

            delay = float(self.cfg.get("request_delay", 0.6))
            limit = int(self.cfg.get("page_limit", 50))
            show_existing = bool(self.cfg.get("show_existing_on_start", False))
            batch = []

            targets = list(self.targets)
            self.stats["cycle_n"] = len(targets)
            for i, (gid, title) in enumerate(targets, 1):
                if not self.scanning:
                    break
                self.stats["cycle_i"] = i
                self.stats["current"] = title

                # Выбираем рабочий клиент из пула аккаунтов (round-robin)
                client = self.scanner_clients[self._client_idx] if self.scanner_clients else self.user
                self._client_idx = (self._client_idx + 1) % max(1, len(self.scanner_clients))

                try:
                    gifts, users = await scanner.resale_page(client, gid, limit)
                except FloodWaitError as e:
                    self.log(f"FloodWait {e.seconds} сек на {gid}")
                    await asyncio.sleep(e.seconds + 1)
                    continue
                except RPCError as e:
                    self.log(f"{title}: {e.__class__.__name__}")
                    await asyncio.sleep(delay)
                    continue

                check_owner = owner_mod.wanted(self.cfg)
                for g in gifts:
                    item = parse(g, title, users)
                    if item is None or item.key in self.seen:
                        continue
                    if not self.primed and not show_existing:
                        self.seen.add(item.key)
                        continue
                    if not passes(self.cfg, item):
                        self.seen.add(item.key)
                        self.stats["skip_filter"] += 1
                        continue
                    if check_owner and not await self._owner_ok(item, users):
                        self.seen.add(item.key)
                        self.stats["skip_owner"] += 1
                        continue
                    item.ts = time.time()
                    self.stats["found"] += 1
                    self.stats["last_found"] = item.ts
                    batch.append((item, users))
                    # Отправляем сразу после обнаружения, не ждём завершения
                    # обхода всех коллекций. Лот помечается просмотренным
                    # только после успешной доставки: временная ошибка Telegram
                    # не должна навсегда терять найденный подарок.
                    if await self._broadcast([(item, users)]):
                        self.seen.add(item.key)

                await asyncio.sleep(delay)

            self.primed = True
            self.seen.save()
            self.stats["cycles"] += 1
            self.log(
                f"круг {self.stats['cycles']}: коллекций {len(targets)}, "
                f"новых лотов {len(batch)}, отсеяно "
                f"{self.stats['skip_owner'] + self.stats['skip_filter']}, "
                f"подписчиков {len(self.subs)}"
            )
            await self._refresh_hud(force=True)
            await asyncio.sleep(float(self.cfg.get("poll_interval", 20)))

    async def _owner_ok(self, item, users: dict) -> bool:
        client = self.scanner_clients[self._client_idx] if self.scanner_clients else self.user
        try:
            info = await self.owners.info(client, users.get(item.owner_id))
        except FloodWaitError as e:
            self.log(f"FloodWait на владельце: {e.seconds} сек")
            await asyncio.sleep(e.seconds + 1)
            return False
        ok, code, why = owner_mod.verdict(self.cfg, info)
        if not ok:
            by = self.stats["skip_by"]
            by[code] = by.get(code, 0) + 1
            self.log(f"{item.title} #{item.num}: пропуск — {why}")
        return ok

    async def _broadcast(self, batch: list) -> int:
        if not batch:
            return 0

        grp_cfg = self.cfg.get("group_settings", {})
        grp_enabled = grp_cfg.get("enabled", True)
        group_id = grp_cfg.get("group_id")
        topics_map = grp_cfg.get("topics", {})
        disabled_cats = set(self.cfg.get("disabled_categories", []))

        sent_before = self.stats["sent"]
        for entry in batch[:MAX_PER_CYCLE]:
            if not self.scanning:
                break

            item, users = entry
            owner_info = None

            # 1. Отправка в супергруппу по топикам форума
            if grp_enabled and group_id:
                if not any(topics_map.values()):
                    _bound, _error = await self._auto_bind_group_topics(group_id)
                    topics_map = self.cfg.get("group_settings", {}).get("topics", {})

                if not any(topics_map.values()):
                    warning = f"no-topics:{group_id}"
                    if self._group_warning != warning:
                        self._group_warning = warning
                        self.log(
                            f"Группа {group_id} подключена, но топики не привязаны. "
                            "Выполните /setup_group или /bind <ключ> в темах."
                        )
                else:
                    self._group_warning = ""

                seller = users.get(item.owner_id) if users else None
                owner_info = self.owners._data.get(item.owner_id, (0, None))[1] if hasattr(self.owners, "_data") else None
                # Географические категории требуют данных полного профиля.
                # Раньше профиль загружался только при включённых фильтрах
                # владельца, поэтому обычный режим не мог определить страну.
                if owner_info is None and seller is not None:
                    client = self.scanner_clients[self._client_idx] if self.scanner_clients else self.user
                    try:
                        owner_info = await self.owners.info(
                            client, seller, with_counts=False
                        )
                    except FloodWaitError as exc:
                        self.log(
                            f"FloodWait {exc.seconds} сек при определении "
                            f"категории {item.title} #{item.num}; "
                            "использую данные из выдачи"
                        )
                    except RPCError as exc:
                        self.log(
                            f"Профиль для категории {item.title} #{item.num}: "
                            f"{exc.__class__.__name__}"
                        )
                matched_cats = categories.classify(item, owner_info=owner_info, user_obj=seller)
                cat_key = categories.primary_category(
                    matched_cats,
                    disabled=disabled_cats,
                    topics=topics_map,
                )
                if not cat_key:
                    # Не теряем лоты, которые не попали в диапазон цены
                    # или не имеют специальных признаков. Для них используем
                    # общий ценовой топик, а если он отключён — первый
                    # доступный топик группы.
                    fallback = "price_300_1000"
                    if (fallback not in disabled_cats
                            and topics_map.get(fallback)):
                        cat_key = fallback
                    else:
                        cat_key = next(
                            (key for key in categories.CATEGORY_PRIORITY
                             if key not in disabled_cats and topics_map.get(key)),
                            None,
                        )
                topic_id = topics_map.get(cat_key) if cat_key else None
                if topic_id:
                    rendered = render(item, owner_info)
                    for attempt in range(1, GROUP_SEND_ATTEMPTS + 1):
                        try:
                            # Не обрываем запрос искусственным трёхсекундным
                            # тайм-аутом: Telegram нередко отвечает дольше, а
                            # отменённый запрос мог уже создать сообщение.
                            sent = await self.bot.send_message(
                                int(group_id),
                                rendered,
                                reply_to=int(topic_id),
                                buttons=work_button(),
                                parse_mode="html",
                                link_preview=True,
                            )
                            self._group_lots[(int(group_id), int(sent.id))] = (item, owner_info, seller)
                            self.stats["sent"] += 1
                            if self.stats["sent"] % 25 == 0:
                                self.log(f"Прогресс рассылки: {self.stats['sent']} отправлено")
                            break
                        except FloodWaitError as exc:
                            self.log(
                                f"FloodWait {exc.seconds} сек при отправке "
                                f"{item.title} #{item.num} в топик {topic_id}"
                            )
                            await asyncio.sleep(exc.seconds + 1)
                        except (RPCError, OSError) as exc:
                            self.log(
                                f"Ошибка отправки {item.title} #{item.num} "
                                f"в группу {group_id}, топик {topic_id}, "
                                f"попытка {attempt}/{GROUP_SEND_ATTEMPTS}: "
                                f"{exc.__class__.__name__}: {exc}"
                            )
                            if attempt < GROUP_SEND_ATTEMPTS:
                                await asyncio.sleep(GROUP_SEND_RETRY_DELAY * attempt)
                        except Exception as exc:  # noqa: BLE001
                            self.log(
                                f"Неожиданная ошибка отправки {item.title} "
                                f"#{item.num} в группу {group_id}, топик "
                                f"{topic_id}: {exc.__class__.__name__}: {exc}"
                            )
                            break
                elif self._group_warning != f"no-route:{group_id}":
                    self._group_warning = f"no-route:{group_id}"
                    self.log(
                        f"Не найден топик для лота {item.title} #{item.num}; "
                        "проверьте привязку ценовой категории"
                    )

            await asyncio.sleep(SEND_PAUSE)

        sent_now = self.stats["sent"] - sent_before
        if len(batch) > MAX_PER_CYCLE:
            self.log(f"Пачка ограничена {MAX_PER_CYCLE} лотами; остальные останутся для следующего прохода")
        self.log(f"Отправлено лотов: {sent_now}")
        return sent_now

    async def _safe_send(self, chat_id: int, text: str, btns=None,
                         preview: bool = False) -> None:
        try:
            await self.bot.send_message(chat_id, text, parse_mode="html", buttons=btns, link_preview=preview)
        except FloodWaitError as e:
            self.log(f"Sender в лимите, жду {e.seconds} сек")
            await asyncio.sleep(e.seconds + 1)
        except RPCError as e:
            self.log(f"Не отправить в {chat_id}: {e.__class__.__name__}")
            if e.__class__.__name__ in ("UserIsBlockedError", "ChatWriteForbiddenError", "InputUserDeactivatedError") or "USER_IS_BLOCKED" in str(e) or "CHAT_WRITE_FORBIDDEN" in str(e):
                self.drop_sub(chat_id)
        except ValueError as e:
            if "Could not find the input entity" in str(e):
                self.log(f"⚠ Не могу отправить сообщение в {chat_id}: бот ещё не видел этого пользователя в текущей сессии. Напишите боту /start!")
            else:
                self.log(f"ValueError в {chat_id}: {e}")

    def log(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {text}", flush=True)
