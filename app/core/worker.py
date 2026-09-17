"""Фоновый поток: своя asyncio-петля + клиент Telethon.

GUI общается с ним только через сигналы и очередь команд,
поэтому интерфейс никогда не подвисает на сетевых запросах.
"""
import asyncio
import threading
import time

from PySide6.QtCore import QThread, Signal
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.tl import functions

from .. import config
from . import memory
from . import owner as owner_mod
from . import scanner
from .models import parse, passes


class Cancelled(Exception):
    """Пользователь закрыл окно ввода номера/кода/пароля."""


class TgWorker(QThread):
    status = Signal(str, str)          # текст, уровень: info | ok | warn | err
    authorized = Signal(str)           # имя аккаунта
    need_phone = Signal()
    need_code = Signal()
    need_password = Signal(str)        # подсказка к облачному паролю
    collections = Signal(list)         # [{id, title, resale, total}]
    found = Signal(object)             # Listing
    progress = Signal(str, int, int)   # коллекция, индекс, всего
    cycle_done = Signal(int, float)    # найдено за круг, пауза до следующего
    scan_state = Signal(bool)
    logged_out = Signal()

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.client: TelegramClient | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._answer: asyncio.Future | None = None
        self._cmds: asyncio.Queue | None = None
        self._scanning = False
        self._quit = False
        self._seen = memory.SeenStore(config.data_dir() / "seen.json")
        self._targets: list[tuple[int, str]] = []
        self._primed = False       # первый (холостой) проход уже сделан
        self._owners = owner_mod.OwnerCache()

    # ---------- вызывается из GUI-потока ----------

    def post(self, name: str, arg=None) -> None:
        """Положить команду в очередь воркера."""
        self._ready.wait(10)
        if self.loop and self._cmds is not None:
            self.loop.call_soon_threadsafe(self._cmds.put_nowait, (name, arg))

    def submit(self, value) -> None:
        """Ответ на need_phone / need_code / need_password (None = отмена)."""
        fut, self._answer = self._answer, None
        if fut and self.loop and not fut.done():
            self.loop.call_soon_threadsafe(fut.set_result, value)

    def set_targets(self, targets) -> None:
        self._targets = list(targets)

    @property
    def scanning(self) -> bool:
        return self._scanning

    def stop_scan(self) -> None:
        self._scanning = False

    def shutdown(self) -> None:
        self._scanning = False
        self._quit = True
        self.post("quit")

    def reset_seen(self) -> None:
        self._seen.clear()
        self._primed = False

    # ---------- внутреннее, в потоке воркера ----------

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Cancelled:
            pass
        except Exception as e:                       # noqa: BLE001
            self.status.emit(f"Критическая ошибка: {e}", "err")
        finally:
            try:
                self.loop.run_until_complete(self._close())
            except Exception:                        # noqa: BLE001
                pass
            self.loop.close()

    async def _close(self) -> None:
        if self.client and self.client.is_connected():
            await self.client.disconnect()

    async def _ask(self, signal, arg=None):
        self._answer = self.loop.create_future()
        if arg is None:
            signal.emit()
        else:
            signal.emit(arg)
        value = await self._answer
        if value is None:
            raise Cancelled()
        return value

    async def _main(self) -> None:
        self._cmds = asyncio.Queue()
        self._ready.set()

        self.client = TelegramClient(
            str(config.SESSION_PATH),
            int(self.cfg["api_id"]),
            self.cfg["api_hash"],
            device_model="TG Gift Radar",
            system_version="Windows 10",
            app_version="1.0",
        )
        self.status.emit("Подключаюсь к Telegram...", "info")
        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self._login()

        me = await self.client.get_me()
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        name = name or me.username or str(me.id)
        self.authorized.emit(name)
        self.status.emit(f"Вошли как {name}", "ok")
        await self._owners.load_me(self.client)
        known = self._seen.load()
        if known:
            self._primed = True
            self.status.emit(f"Помню {known} лотов с прошлых запусков", "info")

        await self._load_collections()

        while not self._quit:
            cmd, _arg = await self._cmds.get()
            if cmd == "quit":
                break
            if cmd == "scan":
                await self._scan_loop()
            elif cmd == "refresh":
                await self._load_collections()
            elif cmd == "logout":
                await self.client.log_out()
                self.logged_out.emit()
                break

    async def _login(self) -> None:
        phone = await self._ask(self.need_phone)
        while True:
            try:
                sent = await self.client.send_code_request(phone)
                break
            except PhoneNumberInvalidError:
                self.status.emit("Неверный номер телефона", "err")
                phone = await self._ask(self.need_phone)
            except FloodWaitError as e:
                self.status.emit(f"Telegram просит подождать {e.seconds} сек", "err")
                raise Cancelled()

        while True:
            code = await self._ask(self.need_code)
            try:
                await self.client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
                return
            except PhoneCodeInvalidError:
                self.status.emit("Неверный код, попробуйте ещё раз", "warn")
            except PhoneCodeExpiredError:
                self.status.emit("Код истёк, запрашиваю новый", "warn")
                sent = await self.client.send_code_request(phone)
            except SessionPasswordNeededError:
                hint = ""
                try:
                    hint = (await self.client(functions.account.GetPasswordRequest())).hint or ""
                except RPCError:
                    pass
                while True:
                    password = await self._ask(self.need_password, hint or " ")
                    try:
                        await self.client.sign_in(password=password)
                        return
                    except RPCError:
                        self.status.emit("Неверный облачный пароль", "warn")

    async def _load_collections(self) -> None:
        self.status.emit("Загружаю каталог коллекций...", "info")
        try:
            items = await scanner.catalog(self.client)
        except FloodWaitError as e:
            self.status.emit(f"FloodWait {e.seconds} сек на каталоге", "err")
            return
        self.collections.emit(items)
        self.status.emit(f"Коллекций в каталоге: {len(items)}", "ok")

    async def _scan_loop(self) -> None:
        if not self._targets:
            self.status.emit("Не выбрано ни одной коллекции", "warn")
            return

        self._scanning = True
        self.scan_state.emit(True)
        interval = float(self.cfg.get("poll_interval", 20))
        delay = float(self.cfg.get("request_delay", 0.6))
        limit = int(self.cfg.get("page_limit", 50))
        show_existing = bool(self.cfg.get("show_existing_on_start", False))

        while self._scanning:
            new_count = 0
            total = len(self._targets)
            for i, (gid, title) in enumerate(self._targets, 1):
                if not self._scanning:
                    break
                self.progress.emit(title, i, total)
                try:
                    gifts, users = await scanner.resale_page(self.client, gid, limit)
                except FloodWaitError as e:
                    self.status.emit(f"FloodWait: жду {e.seconds} сек", "warn")
                    await self._sleep(e.seconds + 1)
                    continue
                except RPCError as e:
                    self.status.emit(f"{title}: {e.__class__.__name__}", "warn")
                    await self._sleep(delay)
                    continue

                check_owner = owner_mod.wanted(self.cfg)
                for g in gifts:
                    item = parse(g, title, users)
                    if item is None or item.key in self._seen:
                        continue
                    self._seen.add(item.key)
                    if not self._primed and not show_existing:
                        continue          # первый круг только запоминает текущий рынок
                    if not passes(self.cfg, item):
                        continue
                    if check_owner and not await self._owner_ok(item, users):
                        continue
                    item.ts = time.time()
                    new_count += 1
                    self.found.emit(item)

                await self._sleep(delay)

            self._primed = True
            self._seen.save()
            if not self._scanning:
                break
            self.cycle_done.emit(new_count, interval)
            await self._sleep(interval)

        self.scan_state.emit(False)
        self.status.emit("Сканирование остановлено", "info")

    async def _owner_ok(self, item, users: dict) -> bool:
        """Фильтры по владельцу: число подарков, NFT и возможность написать."""
        try:
            info = await self._owners.info(self.client, users.get(item.owner_id))
        except FloodWaitError as e:
            self.status.emit(f"FloodWait на владельце: {e.seconds} сек", "warn")
            await self._sleep(e.seconds + 1)
            return False
        ok, _code, why = owner_mod.verdict(self.cfg, info)
        if not ok:
            self.status.emit(f"{item.title} #{item.num}: пропуск — {why}", "info")
        return ok

    async def _sleep(self, seconds: float) -> None:
        """Сон, который сразу прерывается кнопкой «Стоп»."""
        end = time.monotonic() + seconds
        while self._scanning and time.monotonic() < end:
            await asyncio.sleep(min(0.25, max(0.0, end - time.monotonic())))
