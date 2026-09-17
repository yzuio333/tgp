"""Демо-воркер: тот же набор сигналов, что у TgWorker, но без сети.

Нужен, чтобы посмотреть интерфейс и настройки, пока нет ключей API.
Генерирует правдоподобные лоты со случайными атрибутами.
"""
import random
import time

from PySide6.QtCore import QObject, QTimer, Signal

from .models import Listing, passes

COLLECTIONS = [
    ("Plush Pepe", 0x4A3AFF, 0x120A45),
    ("Durov's Cap", 0x1FA97C, 0x08301F),
    ("Precious Peach", 0xFF7A59, 0x5C1B10),
    ("Signet Ring", 0xC9A227, 0x3A2E06),
    ("Astral Shard", 0x00B8D9, 0x073445),
    ("Eternal Rose", 0xE5405E, 0x400B16),
    ("Swiss Watch", 0x8D93A5, 0x23262E),
    ("Heroic Helmet", 0x7B61FF, 0x1B1140),
]
MODELS = ["Classic", "Golden", "Frost", "Obsidian", "Neon", "Royal", "Blush", "Void"]
BACKDROPS = ["Onyx Black", "Emerald", "Sunset", "Deep Sea", "Amber", "Ivory", "Plum"]
SYMBOLS = ["Diamond", "Star", "Heart", "Crown", "Comet", "Anchor", "Flame"]


class DemoWorker(QObject):
    """Полная замена TgWorker для режима без Telegram."""

    status = Signal(str, str)
    authorized = Signal(str)
    need_phone = Signal()
    need_code = Signal()
    need_password = Signal(str)
    collections = Signal(list)
    found = Signal(object)
    progress = Signal(str, int, int)
    cycle_done = Signal(int, float)
    scan_state = Signal(bool)
    logged_out = Signal()

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._scanning = False
        self._targets: list = []
        self._counter = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ---- интерфейс, совместимый с TgWorker ----

    @property
    def scanning(self) -> bool:
        return self._scanning

    def start(self) -> None:
        QTimer.singleShot(400, self._greet)

    def wait(self, msec: int = 0) -> bool:
        return True

    def submit(self, value) -> None:
        pass

    def set_targets(self, targets) -> None:
        self._targets = list(targets)

    def reset_seen(self) -> None:
        pass

    def stop_scan(self) -> None:
        if not self._scanning:
            return
        self._scanning = False
        self._timer.stop()
        self.scan_state.emit(False)
        self.status.emit("Демо остановлено", "info")

    def shutdown(self) -> None:
        self.stop_scan()

    def post(self, name: str, arg=None) -> None:
        if name == "scan":
            self._start_scan()
        elif name == "refresh":
            self._emit_collections()
        elif name in ("logout", "quit"):
            self.stop_scan()

    # ---- внутреннее ----

    def _greet(self) -> None:
        self.authorized.emit("Демо-режим")
        self.status.emit("Демо: данные придуманы, Telegram не используется", "warn")
        self._emit_collections()

    def _emit_collections(self) -> None:
        items = [
            {"id": i, "title": name, "resale": random.randint(12, 400),
             "total": random.choice([1000, 2000, 5000, 10000])}
            for i, (name, _c, _e) in enumerate(COLLECTIONS, 1)
        ]
        self.collections.emit(items)

    def _start_scan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.scan_state.emit(True)
        self.status.emit("Демо: лоты появляются каждые пару секунд", "ok")
        self._timer.start(1600)

    def _tick(self) -> None:
        if not self._targets:
            return
        gid, title = random.choice(self._targets)
        idx = next((i for i, (n, _c, _e) in enumerate(COLLECTIONS) if n == title), 0)
        _name, center, edge = COLLECTIONS[idx]

        ton = random.random() < 0.2
        total = random.choice([1000, 2000, 5000, 10000])
        item = Listing(
            gift_id=gid,
            num=random.randint(1, total),
            title=title,
            slug=f"{title.replace(chr(39), '').replace(' ', '')}-{random.randint(1, total)}",
            price=round(random.uniform(3, 90), 1) if ton else random.randrange(500, 250_000, 100),
            currency="ton" if ton else "stars",
            issued=random.randint(int(total * 0.4), total),
            total=total,
            model=random.choice(MODELS),
            model_rarity=random.randint(3, 300),
            backdrop=random.choice(BACKDROPS),
            backdrop_rarity=random.randint(3, 300),
            symbol=random.choice(SYMBOLS),
            symbol_rarity=random.randint(3, 300),
            center_color=center,
            edge_color=edge,
            text_color=0xFFFFFF,
            owner=random.choice(["", "Кит", "Коллекционер", "Gifts Shop"]),
            owner_username=random.choice(["", "whale", "collector", "gifts_shop"]),
            collection=title,
            ts=time.time(),
            tags=random.choice([[], [], ["Premium"], ["Crafted"], ["TON only"]]),
        )
        if not passes(self.cfg, item):
            return

        self._counter += 1
        self.progress.emit(title, random.randint(1, len(self._targets)), len(self._targets))
        self.found.emit(item)
        if self._counter % 6 == 0:
            self.cycle_done.emit(6, float(self.cfg.get("poll_interval", 20)))
