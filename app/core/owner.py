"""Проверка владельца лота: сколько у него подарков и можно ли ему написать.

Каждая проверка — это 1–2 дополнительных запроса к API, поэтому результат
кэшируется на владельца: один продавец обычно выставляет сразу несколько лотов.
"""
import re
import time

from telethon.errors import FloodWaitError, RPCError
from telethon.tl import functions, types

TTL = 1800          # сколько секунд держать данные о владельце, сек

# страны, где номер телефона говорит о русскоязычном продавце
RU_COUNTRIES = {"RU", "BY", "KZ", "KG", "UA"}
CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")


class OwnerInfo:
    """Что удалось узнать о продавце."""

    def __init__(self, known: bool = False, plain: int = 0, nft: int = 0,
                 can_write: bool = False, reason: str = "",
                 is_ru: bool = False, ru_hint: str = "",
                 country: str = "", lang: str = "", about: str = ""):
        self.known = known          # удалось ли вообще опросить владельца
        self.plain = plain          # обычных подарков в профиле
        self.nft = nft              # уникальных (NFT) в профиле
        self.can_write = can_write
        self.reason = reason        # почему писать нельзя
        self.is_ru = is_ru          # похоже ли, что продавец русскоязычный
        self.ru_hint = ru_hint      # по какому признаку решили
        self.country = country
        self.lang = lang
        self.about = about

    def __repr__(self) -> str:
        return (f"OwnerInfo(known={self.known}, plain={self.plain}, nft={self.nft}, "
                f"can_write={self.can_write}, is_ru={self.is_ru}, country={self.country!r}, "
                f"hint={self.ru_hint!r}, reason={self.reason!r})")


def wanted(cfg: dict) -> bool:
    """Нужно ли вообще опрашивать владельцев при текущих настройках."""
    return bool(int(cfg.get("max_owner_gifts", 0) or 0)
                or int(cfg.get("max_owner_nft", 0) or 0)
                or cfg.get("only_writable", False)
                or cfg.get("only_russian", False)
                or cfg.get("skip_hidden_owner", False))


def verdict(cfg: dict, info: OwnerInfo) -> tuple[bool, str, str]:
    """Пропускать ли лот. Возвращает (ок, код причины, текст).

    Владелец на резейле сплошь и рядом скрыт — Telegram просто не отдаёт
    его в выдаче маркета. Такие лоты по умолчанию НЕ режем, иначе фильтр
    выкашивает почти всё; отсечь их можно галочкой skip_hidden_owner.
    """
    if not info.known:
        if cfg.get("skip_hidden_owner", False):
            return False, "hidden", "владелец скрыт"
        return True, "", ""

    limit_gifts = int(cfg.get("max_owner_gifts", 0) or 0)
    if limit_gifts and info.plain > limit_gifts:
        return False, "gifts", f"подарков {info.plain} > {limit_gifts}"

    limit_nft = int(cfg.get("max_owner_nft", 0) or 0)
    if limit_nft and info.nft > limit_nft:
        return False, "nft", f"NFT {info.nft} > {limit_nft}"

    if cfg.get("only_writable", False) and not info.can_write:
        return False, "write", info.reason or "нельзя написать"

    if cfg.get("only_russian", False) and not info.is_ru:
        return False, "ru", f"не русскоязычный ({info.ru_hint})"

    return True, "", ""


class OwnerCache:
    def __init__(self, ttl: int = TTL):
        self.ttl = ttl
        self._data: dict[int, tuple[float, OwnerInfo]] = {}
        self.me_premium = False

    def forget(self) -> None:
        self._data.clear()

    async def load_me(self, client) -> None:
        """Свой Premium важен: без него закрытым аккаунтам не написать."""
        try:
            me = await client.get_me()
            self.me_premium = bool(getattr(me, "premium", False))
        except RPCError:
            self.me_premium = False

    async def info(self, client, user) -> OwnerInfo:
        """user — объект User из ответа маркета (или None, если владелец скрыт)."""
        if user is None:
            return OwnerInfo(known=False, reason="владелец скрыт")

        cached = self._data.get(user.id)
        if cached and time.time() - cached[0] < self.ttl:
            return cached[1]

        info = await self._fetch(client, user)
        self._data[user.id] = (time.time(), info)
        return info

    async def _fetch(self, client, user) -> OwnerInfo:
        if getattr(user, "deleted", False):
            return OwnerInfo(known=True, can_write=False, reason="аккаунт удалён")
        if getattr(user, "bot", False):
            return OwnerInfo(known=True, can_write=False, reason="это бот")

        peer = types.InputPeerUser(user.id, user.access_hash or 0)

        try:
            full = await client(functions.users.GetFullUserRequest(peer))
        except FloodWaitError:
            raise
        except RPCError as e:
            return OwnerInfo(known=False, reason=e.__class__.__name__)

        uf = full.full_user
        total = getattr(uf, "stargifts_count", 0) or 0

        # сколько из них обычных: то же обращение, но без уникальных
        plain = 0
        if total:
            try:
                saved = await client(functions.payments.GetSavedStarGiftsRequest(
                    peer=peer, offset="", limit=1, exclude_unique=True,
                ))
                plain = saved.count or 0
            except FloodWaitError:
                raise
            except RPCError:
                plain = 0
        nft = max(0, total - plain)

        can_write, reason = self._writable(uf, user)
        is_ru, ru_hint = self._russian(uf, user)
        country = (getattr(getattr(uf, "settings", None), "phone_country", "") or "").upper()
        lang = (getattr(user, "lang_code", "") or "").lower()
        about = getattr(uf, "about", "") or ""
        return OwnerInfo(known=True, plain=plain, nft=nft,
                         can_write=can_write, reason=reason,
                         is_ru=is_ru, ru_hint=ru_hint,
                         country=country, lang=lang, about=about)

    def _russian(self, uf, user) -> tuple[bool, str]:
        """Похоже ли, что продавец русскоязычный.

        Смотрим на страну номера, язык клиента и кириллицу в профиле —
        точного признака Telegram не отдаёт, поэтому решаем по совокупности.
        """
        country = (getattr(getattr(uf, "settings", None), "phone_country", "") or "").upper()
        if country in RU_COUNTRIES:
            return True, f"номер {country}"

        lang = (getattr(user, "lang_code", "") or "").lower()
        if lang.startswith("ru"):
            return True, "язык ru"

        profile = " ".join(filter(None, [
            getattr(user, "first_name", "") or "",
            getattr(user, "last_name", "") or "",
            getattr(uf, "about", "") or "",
        ]))
        if CYRILLIC.search(profile):
            return True, "кириллица в профиле"

        return False, f"номер {country}" if country else "нет признаков"

    def _writable(self, uf, user) -> tuple[bool, str]:
        """Эвристика «можно ли написать» по данным профиля."""
        if getattr(uf, "contact_require_premium", False) and not self.me_premium:
            return False, "пишут только Premium"

        settings = getattr(uf, "settings", None)
        stars = getattr(settings, "charge_paid_message_stars", 0) or 0
        if stars:
            return False, f"платные сообщения ({stars} ⭐)"

        return True, ""
