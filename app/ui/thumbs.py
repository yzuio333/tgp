"""Загрузка превью подарков с t.me/nft/… через QNetworkAccessManager.

Синглтон: одна очередь на весь GUI, кэш в памяти по (slug, num).
Используем сеть в GUI-потоке (Qt-неблокирующая), поэтому никакие
QThread'ы не нужны — карточки просто просят превью и получают его
сигналом когда придёт.

Подход: HTTP GET страницы t.me/nft/<slug>-<num>, парсим og:image
регуляркой, качаем картинку, кэшируем. Без Telegram API, без FLOOD_WAIT.
Если сайт t.me недоступен — карточка молча остаётся с градиентным
аватаром-инициалами.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest


OG_IMAGE_RE = re.compile(rb'property=["\']og:image["\']\s+content=["\']([^"\']+)')

_UA = (b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       b"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")


class ThumbLoader(QObject):
    """Один экземпляр на приложение — берём через ThumbLoader.instance()."""
    thumb_ready = Signal(str, QPixmap)          # key = "slug-num"

    _instance: "ThumbLoader | None" = None

    @classmethod
    def instance(cls) -> "ThumbLoader":
        if cls._instance is None:
            cls._instance = ThumbLoader()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._nam = QNetworkAccessManager()
        self._cache: dict[str, QPixmap] = {}
        self._in_flight: set[str] = set()

    def cached(self, slug: str, num: int) -> QPixmap | None:
        return self._cache.get(f"{slug}-{num}")

    def request(self, slug: str, num: int) -> None:
        """Асинхронно попросить превью. thumb_ready прилетит когда готово."""
        if not slug:
            return
        key = f"{slug}-{num}"
        if key in self._cache:
            # уже загружено — эмитим сразу, чтобы новый подписчик получил
            self.thumb_ready.emit(key, self._cache[key])
            return
        if key in self._in_flight:
            return
        self._in_flight.add(key)
        url = f"https://t.me/nft/{key}"
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", _UA)
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, k=key: self._on_page(r, k))

    def _on_page(self, reply, key: str) -> None:
        try:
            data = bytes(reply.readAll())
        finally:
            reply.deleteLater()
        m = OG_IMAGE_RE.search(data)
        if not m:
            self._in_flight.discard(key)
            return
        img_url = m.group(1).decode("utf-8", errors="ignore")
        # HTML-entity decode для & → &
        img_url = img_url.replace("&amp;", "&")
        req = QNetworkRequest(QUrl(img_url))
        req.setRawHeader(b"User-Agent", _UA)
        reply2 = self._nam.get(req)
        reply2.finished.connect(lambda r=reply2, k=key: self._on_image(r, k))

    def _on_image(self, reply, key: str) -> None:
        try:
            data = bytes(reply.readAll())
        finally:
            reply.deleteLater()
        self._in_flight.discard(key)
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        self._cache[key] = pix
        self.thumb_ready.emit(key, pix)
