"""Главное окно: сайдбар с настройками + живая лента лотов."""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..core.demo import DemoWorker
from ..core.worker import TgWorker
from . import theme
from .dialogs import ApiKeysDialog, AskDialog
from .widgets import GiftCard


def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("SectionTitle")
    return lbl


class MainWindow(QWidget):
    def __init__(self, cfg: dict, demo: bool = False):
        super().__init__()
        self.cfg = cfg
        self.demo = demo
        self.setObjectName("Root")
        self.setWindowTitle(
            "Gift Radar — ДЕМО (данные придуманы)" if demo
            else "Gift Radar — парсер маркета Telegram"
        )
        self.resize(1180, 780)
        self.setMinimumSize(940, 620)

        self.cards: dict[tuple, GiftCard] = {}
        self.total_found = 0
        self._last_beep = 0.0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar(), 0)
        root.addWidget(self._build_feed(), 1)

        self.worker = DemoWorker(self.cfg) if demo else TgWorker(self.cfg)
        self.worker.status.connect(self.on_status)
        self.worker.authorized.connect(self.on_authorized)
        self.worker.need_phone.connect(self.ask_phone)
        self.worker.need_code.connect(self.ask_code)
        self.worker.need_password.connect(self.ask_password)
        self.worker.collections.connect(self.on_collections)
        self.worker.found.connect(self.on_found)
        self.worker.progress.connect(self.on_progress)
        self.worker.cycle_done.connect(self.on_cycle)
        self.worker.scan_state.connect(self.on_scan_state)
        self.worker.logged_out.connect(self.on_logged_out)
        self.worker.start()

    # ------------------------------------------------------------ сайдбар

    def _build_sidebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(310)
        box = QVBoxLayout(bar)
        box.setContentsMargins(18, 18, 18, 16)
        box.setSpacing(9)

        logo = QLabel("◈  GIFT RADAR")
        logo.setObjectName("Logo")
        box.addWidget(logo)
        sub = QLabel("лоты Telegram Market в реальном времени")
        sub.setObjectName("LogoSub")
        sub.setWordWrap(True)
        box.addWidget(sub)

        self.account = QLabel("не подключено")
        self.account.setObjectName("Muted")
        box.addWidget(self.account)

        self.start_btn = QPushButton("▶   Запустить")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.toggle_scan)
        box.addWidget(self.start_btn)

        box.addWidget(_section("параметры"))
        self.interval = QSpinBox()
        self.interval.setRange(5, 3600)
        self.interval.setSuffix(" сек")
        self.interval.setValue(int(self.cfg["poll_interval"]))
        self.interval.setToolTip("Пауза между полными кругами обхода коллекций")
        box.addLayout(self._row("Круг опроса", self.interval))

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.1, 10.0)
        self.delay.setSingleStep(0.1)
        self.delay.setSuffix(" сек")
        self.delay.setValue(float(self.cfg["request_delay"]))
        self.delay.setToolTip("Пауза между запросами. Меньше 0.4 — риск FloodWait")
        box.addLayout(self._row("Между запросами", self.delay))

        self.limit = QSpinBox()
        self.limit.setRange(10, 100)
        self.limit.setValue(int(self.cfg["page_limit"]))
        self.limit.setToolTip("Сколько свежих лотов проверять в каждой коллекции")
        box.addLayout(self._row("Лотов за запрос", self.limit))

        self.min_price = QSpinBox()
        self.min_price.setRange(0, 100_000_000)
        self.min_price.setSingleStep(100)
        self.min_price.setValue(int(self.cfg["min_price"]))
        box.addLayout(self._row("Цена от, ⭐", self.min_price))

        self.max_price = QSpinBox()
        self.max_price.setRange(0, 100_000_000)
        self.max_price.setSingleStep(100)
        self.max_price.setValue(int(self.cfg["max_price"]))
        self.max_price.setToolTip("0 — без верхней границы")
        box.addLayout(self._row("Цена до, ⭐", self.max_price))

        cur_row = QHBoxLayout()
        cur_lbl = QLabel("Валюта лота")
        cur_lbl.setObjectName("Muted")
        cur_row.addWidget(cur_lbl, 1)
        self.cur_stars = QCheckBox("⭐")
        self.cur_stars.setChecked(bool(self.cfg["cur_stars"]))
        self.cur_stars.setToolTip("Показывать лоты с ценой в звёздах")
        self.cur_ton = QCheckBox("TON")
        self.cur_ton.setChecked(bool(self.cfg["cur_ton"]))
        self.cur_ton.setToolTip("Показывать лоты с ценой в TON")
        cur_row.addWidget(self.cur_stars, 0)
        cur_row.addWidget(self.cur_ton, 0)
        box.addLayout(cur_row)

        box.addWidget(_section("владелец лота"))
        self.max_gifts = QSpinBox()
        self.max_gifts.setRange(0, 10000)
        self.max_gifts.setSpecialValueText("без лимита")
        self.max_gifts.setValue(int(self.cfg["max_owner_gifts"]))
        self.max_gifts.setToolTip(
            "Пропускать лот, если у продавца больше N обычных подарков. 0 — не проверять")
        box.addLayout(self._row("Подарков не больше", self.max_gifts))

        self.max_nft = QSpinBox()
        self.max_nft.setRange(0, 10000)
        self.max_nft.setSpecialValueText("без лимита")
        self.max_nft.setValue(int(self.cfg["max_owner_nft"]))
        self.max_nft.setToolTip(
            "Пропускать лот, если у продавца больше N уникальных подарков (NFT). 0 — не проверять")
        box.addLayout(self._row("NFT не больше", self.max_nft))

        self.only_writable = QCheckBox("Только те, кому можно написать")
        self.only_writable.setChecked(bool(self.cfg["only_writable"]))
        self.only_writable.setToolTip(
            "Скрывать продавцов с закрытыми личными сообщениями, "
            "платными сообщениями и скрытым профилем")
        box.addWidget(self.only_writable)

        self.only_russian = QCheckBox("Только русскоязычные продавцы")
        self.only_russian.setChecked(bool(self.cfg["only_russian"]))
        self.only_russian.setToolTip(
            "Определяется по стране номера, языку клиента и кириллице в профиле")
        box.addWidget(self.only_russian)

        self.skip_hidden = QCheckBox("Прятать лоты со скрытым продавцом")
        self.skip_hidden.setChecked(bool(self.cfg["skip_hidden_owner"]))
        self.skip_hidden.setToolTip(
            "У части лотов Telegram не показывает продавца. По умолчанию они "
            "проходят фильтр, эта галочка их убирает")
        box.addWidget(self.skip_hidden)

        box.addWidget(_section("прочее"))
        self.only_resale = QCheckBox("Только коллекции с резейлом")
        self.only_resale.setChecked(bool(self.cfg["only_active_resale"]))
        self.only_resale.stateChanged.connect(self.refill_collections)
        for cb in (self.cur_stars, self.cur_ton, self.only_writable,
                   self.only_russian, self.skip_hidden):
            cb.stateChanged.connect(self.apply_runtime_settings)
        for sb in (self.max_gifts, self.max_nft):
            sb.valueChanged.connect(self.apply_runtime_settings)
        box.addWidget(self.only_resale)

        self.show_existing = QCheckBox("Показать лоты, что уже висят")
        self.show_existing.setChecked(bool(self.cfg["show_existing_on_start"]))
        self.show_existing.setToolTip(
            "Выключено: первый круг молча запоминает рынок,\n"
            "и вы видите только по-настоящему новые лоты."
        )
        box.addWidget(self.show_existing)

        self.sound = QCheckBox("Звук при новом лоте")
        self.sound.setChecked(bool(self.cfg["sound"]))
        box.addWidget(self.sound)

        box.addWidget(_section("коллекции"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("поиск по названию...")
        self.search.textChanged.connect(self.apply_search)
        box.addWidget(self.search)

        self.col_list = QListWidget()
        self.col_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.col_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.col_list.setMinimumHeight(150)
        box.addWidget(self.col_list, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        for text, fn in (("Все", lambda: self.check_all(True)),
                         ("Снять", lambda: self.check_all(False)),
                         ("Обновить", lambda: self.worker.post("refresh"))):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            row.addWidget(b)
        box.addLayout(row)

        self.status = QLabel("запуск...")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        box.addWidget(self.status)

        logout = QPushButton("Закрыть демо" if self.demo else "Выйти из аккаунта")
        logout.setObjectName("Danger")
        logout.clicked.connect(self.close if self.demo else self.logout)
        box.addWidget(logout)

        # настроек стало много — пусть панель прокручивается на низких экранах
        holder = QScrollArea()
        holder.setObjectName("SidebarScroll")
        holder.setWidget(bar)
        holder.setWidgetResizable(True)
        holder.setFixedWidth(324)
        holder.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return holder

    def _row(self, caption: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(caption)
        lbl.setObjectName("Muted")
        row.addWidget(lbl, 1)
        widget.setFixedWidth(110)
        row.addWidget(widget, 0)
        return row

    # --------------------------------------------------------------- лента

    def _build_feed(self) -> QWidget:
        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(20, 18, 20, 18)
        box.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Новые лоты")
        title.setObjectName("Logo")
        head.addWidget(title)
        head.addStretch(1)

        self.stat_feed = QLabel("0")
        self.stat_feed.setObjectName("StatBig")
        head.addWidget(self._stat_block(self.stat_feed, "в ленте"))
        self.stat_total = QLabel("0")
        self.stat_total.setObjectName("StatBig")
        head.addWidget(self._stat_block(self.stat_total, "всего найдено"))

        clear = QPushButton("Убрать все")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(self.clear_feed)
        head.addWidget(clear)
        box.addLayout(head)

        self.progress = QLabel("ожидание запуска")
        self.progress.setObjectName("Muted")
        box.addWidget(self.progress)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER};")
        box.addWidget(line)

        self.scroll, self.feed, self.empty = self._make_feed_area(
            "Здесь появятся подарки, выставленные на маркет.\n\n"
            "Отметьте коллекции слева и нажмите «Запустить».\n"
            "Кнопка «✓ Готово» на карточке убирает лот из ленты."
        )
        box.addWidget(self.scroll, 1)
        return panel

    def _make_feed_area(self, empty_text: str) -> tuple:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName("FeedHolder")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 4, 8, 4)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        empty = QLabel(empty_text)
        empty.setObjectName("Empty")
        empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(empty)
        scroll.setWidget(holder)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setObjectName("FeedViewport")
        return scroll, layout, empty

    def _stat_block(self, value: QLabel, caption: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 0, 14, 0)
        v.setSpacing(0)
        value.setAlignment(Qt.AlignCenter)
        cap = QLabel(caption)
        cap.setObjectName("StatCaption")
        cap.setAlignment(Qt.AlignCenter)
        v.addWidget(value)
        v.addWidget(cap)
        return w

    # ------------------------------------------------------------ слоты

    def on_status(self, text: str, level: str) -> None:
        color = theme.LEVEL_COLORS.get(level, theme.MUTED)
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(text)

    def on_authorized(self, name: str) -> None:
        self.account.setText(f"● {name}")
        self.account.setStyleSheet(f"color: {theme.GREEN};")
        self.start_btn.setEnabled(True)

    def ask_phone(self) -> None:
        self._ask("Вход в Telegram", "Номер телефона в международном формате.",
                  "+7 900 000 00 00", False)

    def ask_code(self) -> None:
        self._ask("Код подтверждения", "Telegram прислал код в приложение.",
                  "12345", False)

    def ask_password(self, hint: str) -> None:
        note = f"Подсказка: {hint}" if hint.strip() else ""
        self._ask("Облачный пароль", f"Включена двухфакторная защита. {note}",
                  "пароль", True)

    def _ask(self, title: str, hint: str, placeholder: str, secret: bool) -> None:
        dlg = AskDialog(title, hint, placeholder, secret, self)
        self.worker.submit(dlg.value if dlg.exec() else None)

    def on_collections(self, items: list) -> None:
        self._all_collections = items
        self.refill_collections()

    def refill_collections(self) -> None:
        items = getattr(self, "_all_collections", [])
        explicit = bool(self.cfg.get("collections_set"))
        chosen = set(self.cfg.get("collections") or [])
        only = self.only_resale.isChecked()
        self.col_list.clear()
        for c in items:
            if only and not c["resale"]:
                continue
            label = f"{c['title']}   ({c['resale']})" if c["resale"] else c["title"]
            it = QListWidgetItem(label)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setData(Qt.UserRole, c["id"])
            it.setData(Qt.UserRole + 1, c["title"])
            checked = (c["id"] in chosen) if explicit else bool(c["resale"])
            it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.col_list.addItem(it)
        self.apply_search(self.search.text())

    def apply_search(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.col_list.count()):
            it = self.col_list.item(i)
            it.setHidden(bool(needle) and needle not in it.text().lower())

    def check_all(self, state: bool) -> None:
        for i in range(self.col_list.count()):
            it = self.col_list.item(i)
            if not it.isHidden():
                it.setCheckState(Qt.Checked if state else Qt.Unchecked)

    def selected_targets(self) -> list:
        out = []
        for i in range(self.col_list.count()):
            it = self.col_list.item(i)
            if it.checkState() == Qt.Checked:
                out.append((it.data(Qt.UserRole), it.data(Qt.UserRole + 1)))
        return out

    def toggle_scan(self) -> None:
        if self.worker.scanning:
            self.worker.stop_scan()
            return
        targets = self.selected_targets()
        if not targets:
            QMessageBox.information(self, "Gift Radar",
                                    "Отметьте хотя бы одну коллекцию.")
            return
        if not self.cur_stars.isChecked() and not self.cur_ton.isChecked():
            QMessageBox.information(self, "Gift Radar",
                                    "Отметьте хотя бы одну валюту: ⭐ или TON.")
            return
        self.collect_settings()
        self.apply_runtime_settings()
        self.worker.set_targets(targets)
        self.worker.post("scan")

    def collect_settings(self) -> None:
        if self.demo:
            return          # демо не трогает сохранённые настройки
        self.cfg.update({
            "poll_interval": self.interval.value(),
            "request_delay": self.delay.value(),
            "page_limit": self.limit.value(),
            "min_price": self.min_price.value(),
            "max_price": self.max_price.value(),
            "max_owner_gifts": self.max_gifts.value(),
            "max_owner_nft": self.max_nft.value(),
            "only_writable": self.only_writable.isChecked(),
            "only_russian": self.only_russian.isChecked(),
            "skip_hidden_owner": self.skip_hidden.isChecked(),
            "cur_stars": self.cur_stars.isChecked(),
            "cur_ton": self.cur_ton.isChecked(),
            "only_active_resale": self.only_resale.isChecked(),
            "show_existing_on_start": self.show_existing.isChecked(),
            "sound": self.sound.isChecked(),
            "collections": [gid for gid, _ in self.selected_targets()],
            "collections_set": True,
        })
        config.save(self.cfg)

    def apply_runtime_settings(self) -> None:
        """Прокинуть значения полей воркеру, не записывая их на диск."""
        self.cfg.update({
            "poll_interval": self.interval.value(),
            "request_delay": self.delay.value(),
            "page_limit": self.limit.value(),
            "min_price": self.min_price.value(),
            "max_price": self.max_price.value(),
            "max_owner_gifts": self.max_gifts.value(),
            "max_owner_nft": self.max_nft.value(),
            "only_writable": self.only_writable.isChecked(),
            "only_russian": self.only_russian.isChecked(),
            "skip_hidden_owner": self.skip_hidden.isChecked(),
            "cur_stars": self.cur_stars.isChecked(),
            "cur_ton": self.cur_ton.isChecked(),
            "show_existing_on_start": self.show_existing.isChecked(),
        })

    def on_scan_state(self, running: bool) -> None:
        self.start_btn.setText("■   Остановить" if running else "▶   Запустить")
        if not running:
            self.progress.setText("остановлено")

    def on_progress(self, title: str, i: int, total: int) -> None:
        self.progress.setText(f"проверяю {title}  ·  {i} из {total}")

    def on_cycle(self, new_count: int, wait_s: float) -> None:
        self.progress.setText(
            f"круг завершён · новых лотов: {new_count} · "
            f"следующий через {wait_s:.0f} сек"
        )

    def on_found(self, item) -> None:
        # общая лента
        self.empty.hide()
        card = GiftCard(item)
        card.dismissed.connect(self.on_dismissed)
        self.feed.insertWidget(0, card)
        self.cards[item.key] = card

        self.total_found += 1
        self.stat_total.setText(str(self.total_found))
        self.stat_feed.setText(str(len(self.cards)))

        limit = int(self.cfg.get("max_cards", 300))
        while len(self.cards) > limit:
            oldest_key = next(iter(self.cards))
            widget = self.cards.pop(oldest_key)
            widget.setParent(None)
            widget.deleteLater()

        self.beep()

    def on_dismissed(self, item) -> None:
        self.cards.pop(item.key, None)
        self.stat_feed.setText(str(len(self.cards)))
        if not self.cards:
            self.empty.show()

    def clear_feed(self) -> None:
        for card in list(self.cards.values()):
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        self.stat_feed.setText("0")
        self.empty.show()

    def beep(self) -> None:
        if not self.sound.isChecked():
            return
        now = time.time()
        if now - self._last_beep < 2.0:
            return
        self._last_beep = now
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:                      # noqa: BLE001
            pass

    def logout(self) -> None:
        ok = QMessageBox.question(
            self, "Выход",
            "Отвязать аккаунт? Сессия будет удалена, при следующем запуске "
            "нужно будет войти заново.",
        )
        if ok == QMessageBox.Yes:
            self.worker.stop_scan()
            self.worker.post("logout")

    def on_logged_out(self) -> None:
        try:
            for suffix in ("", ".session"):
                p = config.SESSION_PATH.with_name(config.SESSION_PATH.name + suffix)
                if p.exists():
                    p.unlink()
        except OSError:
            pass
        QMessageBox.information(self, "Gift Radar",
                                "Аккаунт отвязан. Перезапустите программу.")
        self.close()

    def closeEvent(self, event):            # noqa: N802 (Qt naming)
        self.collect_settings()
        self.worker.shutdown()
        self.worker.wait(3000)
        QTimer.singleShot(0, lambda: None)
        event.accept()
