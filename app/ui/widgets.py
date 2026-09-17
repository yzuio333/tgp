"""Карточка подарка и вспомогательные виджеты."""
import time

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QGuiApplication, QPainter,
    QPainterPath, QPixmap, QRadialGradient,
)
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .thumbs import ThumbLoader


def _initials(text: str) -> str:
    parts = [p for p in text.replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


class ElidedLabel(QLabel):
    """Однострочный лейбл: длинный текст обрезается многоточием,
    а не растягивает карточку по ширине."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text: str) -> None:   # noqa: N802 (Qt naming)
        self._full = text
        super().setText(text)
        self.update()

    def paintEvent(self, event):            # noqa: N802 (Qt naming)
        p = QPainter(self)
        metrics = self.fontMetrics()
        text = metrics.elidedText(self._full, Qt.ElideRight, self.width())
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(self.rect(), int(self.alignment()) | Qt.TextSingleLine, text)
        p.end()


class GiftAvatar(QWidget):
    """Кружок в цветах backdrop-а подарка."""

    def __init__(self, center: int, edge: int, text_color: int, label: str, size: int = 58):
        super().__init__()
        self.setFixedSize(size, size)
        self._center = QColor(center)
        self._edge = QColor(edge)
        self._fg = QColor(text_color)
        self._label = label

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        grad = QRadialGradient(r.center().x(), r.top() + r.height() * 0.3, r.width())
        grad.setColorAt(0.0, self._center)
        grad.setColorAt(1.0, self._edge)
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(r)

        f = QFont("Segoe UI", int(r.height() * 0.30))
        f.setBold(True)
        p.setFont(f)
        p.setPen(self._fg)
        p.drawText(r, Qt.AlignCenter, self._label)
        p.end()


class GiftThumb(QWidget):
    """Круглое превью: пока картинка не пришла — градиентный аватар с инициалами.
    Когда ThumbLoader отдаст QPixmap с t.me/nft/… — показывает его, обрезав по кругу.
    """

    def __init__(self, item, size: int = 58):
        super().__init__()
        self.setFixedSize(size, size)
        self._center = QColor(item.center_color)
        self._edge = QColor(item.edge_color)
        self._fg = QColor(item.text_color)
        self._label = _initials(item.collection or item.title)
        self._pix: QPixmap | None = None

        key = f"{item.slug}-{item.num}" if item.slug else ""
        self._key = key
        loader = ThumbLoader.instance()
        cached = loader.cached(item.slug, item.num) if item.slug else None
        if cached is not None:
            self._pix = cached
        elif item.slug:
            loader.thumb_ready.connect(self._on_thumb)
            loader.request(item.slug, item.num)

    def _on_thumb(self, key: str, pix: QPixmap) -> None:
        if key != self._key:
            return
        self._pix = pix
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        # маска по кругу — картинка не должна вылезать за края
        path = QPainterPath()
        path.addEllipse(r)
        p.setClipPath(path)

        if self._pix is not None and not self._pix.isNull():
            # cropped-square-fit по центру
            pw, ph = self._pix.width(), self._pix.height()
            side = min(pw, ph)
            src_x = (pw - side) // 2
            src_y = (ph - side) // 2
            p.drawPixmap(r, self._pix, self._pix.rect().adjusted(
                src_x, src_y, -(pw - side - src_x), -(ph - side - src_y)))
        else:
            grad = QRadialGradient(r.center().x(), r.top() + r.height() * 0.3, r.width())
            grad.setColorAt(0.0, self._center)
            grad.setColorAt(1.0, self._edge)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(r)

            f = QFont("Segoe UI", int(r.height() * 0.30))
            f.setBold(True)
            p.setFont(f)
            p.setPen(self._fg)
            p.setClipping(False)
            p.drawText(r, Qt.AlignCenter, self._label)
        p.end()


class GiftCard(QFrame):
    """Один лот с маркета. Кнопка «Готово» убирает карточку из ленты."""

    dismissed = Signal(object)   # передаёт Listing

    def __init__(self, item):
        super().__init__()
        self.item = item
        self.setObjectName("Card")
        self._anim = None

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(14)

        # круглое превью: картинка NFT с t.me, до загрузки — цветной кружок
        root.addWidget(GiftThumb(item), 0, Qt.AlignVCenter)

        # ---- центральная колонка: название + характеристики ----
        mid = QVBoxLayout()
        mid.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(7)
        title = QLabel(item.title)
        title.setObjectName("CardTitle")
        title.setMinimumWidth(0)
        num = QLabel(f"#{item.num:,}".replace(",", " "))
        num.setObjectName("CardNum")
        top.addWidget(title)
        top.addWidget(num)
        for tag in item.tags:
            lbl = QLabel(tag)
            lbl.setObjectName("Tag")
            top.addWidget(lbl)
        top.addStretch(1)
        mid.addLayout(top)

        chips = []
        if item.model:
            chips.append(f"🧩 {item.model} · {item.model_rarity / 10:.1f}%")
        if item.backdrop:
            chips.append(f"🎨 {item.backdrop} · {item.backdrop_rarity / 10:.1f}%")
        if item.symbol:
            chips.append(f"✦ {item.symbol} · {item.symbol_rarity / 10:.1f}%")
        meta = ElidedLabel("   ".join(chips) or "нет данных об атрибутах")
        meta.setObjectName("CardMeta")
        mid.addWidget(meta)

        extra = []
        if item.supply_text:
            extra.append(f"тираж {item.supply_text}")
        if item.owner_username:
            extra.append(f"@{item.owner_username}"
                         + (f" ({item.owner})" if item.owner else ""))
        elif item.owner:
            extra.append(f"продавец {item.owner}")
        extra.append(time.strftime("%H:%M:%S", time.localtime(item.ts or time.time())))
        sub = ElidedLabel("  ·  ".join(extra))
        sub.setObjectName("CardMeta")
        mid.addWidget(sub)

        root.addLayout(mid, 1)

        # ---- правая колонка: цена и кнопки ----
        right = QVBoxLayout()
        right.setSpacing(8)
        price = QLabel(item.price_text)
        price.setObjectName("CardPrice")
        price.setAlignment(Qt.AlignRight)
        right.addWidget(price)

        btns = QHBoxLayout()
        btns.setSpacing(7)
        if item.url:
            open_btn = QPushButton("Открыть в TG")
            open_btn.setObjectName("CardOpen")
            open_btn.setCursor(Qt.PointingHandCursor)
            open_btn.setToolTip(f"Открыть {item.url} в Telegram-маркете")
            open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(item.url)))
            btns.addWidget(open_btn)

            copy_btn = QPushButton("Копировать")
            copy_btn.setObjectName("CardOpen")
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setToolTip("Скопировать ссылку на подарок в буфер обмена")
            copy_btn.clicked.connect(self._copy_url)
            btns.addWidget(copy_btn)
        if item.owner_link:
            write_btn = QPushButton("Написать")
            write_btn.setObjectName("CardOpen")
            write_btn.setCursor(Qt.PointingHandCursor)
            write_btn.setToolTip(f"Открыть чат с @{item.owner_username}")
            write_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(item.owner_link)))
            btns.addWidget(write_btn)
        done = QPushButton("✓ Готово")
        done.setObjectName("CardDone")
        done.setCursor(Qt.PointingHandCursor)
        done.clicked.connect(self.dismiss)
        btns.addWidget(done)
        right.addLayout(btns)

        root.addLayout(right, 0)

        # плавное появление
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._in = QPropertyAnimation(self._fx, b"opacity", self)
        self._in.setDuration(260)
        self._in.setStartValue(0.0)
        self._in.setEndValue(1.0)
        self._in.setEasingCurve(QEasingCurve.OutCubic)
        self._in.start()

    def _copy_url(self) -> None:
        """Скопировать ссылку на подарок в буфер обмена."""
        if not self.item.url:
            return
        QGuiApplication.clipboard().setText(self.item.url)
        # быстрая визуальная обратная связь: кнопка «Копировать» → «✓ Скопировано»
        for child in self.findChildren(QPushButton):
            if child.text() == "Копировать":
                child.setText("✓ Скопировано")
                # вернуть надпись через 1.2 сек
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1200, lambda b=child: b.setText("Копировать"))
                break

    def dismiss(self) -> None:
        """Схлопнуть карточку и удалить её."""
        self.setEnabled(False)
        h = self.height()

        fade = QPropertyAnimation(self._fx, b"opacity", self)
        fade.setDuration(180)
        fade.setStartValue(self._fx.opacity())
        fade.setEndValue(0.0)

        shrink = QPropertyAnimation(self, b"maximumHeight", self)
        shrink.setDuration(240)
        shrink.setStartValue(h)
        shrink.setEndValue(0)
        shrink.setEasingCurve(QEasingCurve.InCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(shrink)
        group.finished.connect(self._finish)
        self._anim = group           # держим ссылку, иначе анимацию соберёт GC
        group.start()

    def _finish(self) -> None:
        self.dismissed.emit(self.item)
        self.setParent(None)
        self.deleteLater()
