"""Разбор TL-объектов Telegram в простые структуры для UI."""
from dataclasses import dataclass, field

from telethon.tl import types

STARS = "⭐"


def _rarity(attr) -> int:
    """rarity у атрибута -- объект StarGiftAttributeRarity(permille)."""
    r = getattr(attr, "rarity", None)
    if r is None:
        return 0
    return getattr(r, "permille", 0) or 0


def _price(gift) -> tuple[float, str]:
    """Цена лота. resell_amount -- список сумм в разных валютах."""
    amounts = getattr(gift, "resell_amount", None) or []
    stars = ton = None
    for a in amounts:
        if isinstance(a, types.StarsAmount):
            stars = a.amount + (a.nanos or 0) / 1e9
        elif isinstance(a, types.StarsTonAmount):
            ton = a.amount / 1e9
    if stars is not None:
        return stars, "stars"
    if ton is not None:
        return ton, "ton"
    return 0.0, "stars"


@dataclass
class Listing:
    """Один выставленный на маркет подарок."""
    gift_id: int
    num: int
    title: str
    slug: str
    price: float
    currency: str
    issued: int
    total: int
    model: str = ""
    model_rarity: int = 0
    backdrop: str = ""
    backdrop_rarity: int = 0
    symbol: str = ""
    symbol_rarity: int = 0
    center_color: int = 0x3B82F6
    edge_color: int = 0x1E3A8A
    text_color: int = 0xFFFFFF
    owner: str = ""
    owner_id: int = 0
    owner_username: str = ""
    collection: str = ""
    ts: float = 0.0
    tags: list = field(default_factory=list)
    is_on_chain: bool = False
    value_usd_amount: int = 0

    @property
    def is_rich(self) -> bool:
        if self.is_on_chain:
            return True
        if "Black" in self.backdrop:
            return True
        if self.num < 1000:
            return True
        if len(set(str(self.num))) == 1:
            return True
        if self.value_usd_amount > 3000:  # > $30 (Telegram usually stores in cents)
            return True
        return False

    @property
    def key(self) -> tuple:
        return (self.gift_id, self.num)

    @property
    def owner_link(self) -> str:
        return f"https://t.me/{self.owner_username}" if self.owner_username else ""

    @property
    def url(self) -> str:
        return f"https://t.me/nft/{self.slug}" if self.slug else ""

    @property
    def price_text(self) -> str:
        if self.currency == "ton":
            return f"{self.price:,.2f} TON".replace(",", " ")
        return f"{STARS} {self.price:,.0f}".replace(",", " ")

    @property
    def supply_text(self) -> str:
        if self.total:
            return f"{self.issued:,}/{self.total:,}".replace(",", " ")
        return ""


def parse(gift, collection_title: str = "", users: dict | None = None) -> Listing | None:
    """StarGiftUnique -> Listing.

    users — словарь {id: User} из того же ответа маркета: оттуда берём
    юзернейм продавца. Возвращает None, если объект не тот.
    """
    if not isinstance(gift, types.StarGiftUnique):
        return None

    price, currency = _price(gift)
    item = Listing(
        gift_id=gift.gift_id,
        num=gift.num,
        title=gift.title or collection_title or "Gift",
        slug=gift.slug or "",
        price=price,
        currency=currency,
        issued=gift.availability_issued or 0,
        total=gift.availability_total or 0,
        owner=getattr(gift, "owner_name", "") or "",
        owner_id=getattr(getattr(gift, "owner_id", None), "user_id", 0) or 0,
        collection=collection_title,
        is_on_chain=bool(getattr(gift, "gift_address", None) or getattr(gift, "owner_address", None)),
        value_usd_amount=getattr(gift, "value_usd_amount", 0) or 0,
    )

    seller = (users or {}).get(item.owner_id)
    if seller is not None:
        item.owner_username = getattr(seller, "username", "") or ""
        if not item.owner:
            first = getattr(seller, "first_name", "") or ""
            last = getattr(seller, "last_name", "") or ""
            item.owner = (first + " " + last).strip()

    for a in gift.attributes or []:
        if isinstance(a, types.StarGiftAttributeModel):
            item.model, item.model_rarity = a.name, _rarity(a)
        elif isinstance(a, types.StarGiftAttributePattern):
            item.symbol, item.symbol_rarity = a.name, _rarity(a)
        elif isinstance(a, types.StarGiftAttributeBackdrop):
            item.backdrop, item.backdrop_rarity = a.name, _rarity(a)
            item.center_color = a.center_color
            item.edge_color = a.edge_color
            item.text_color = a.text_color

    if getattr(gift, "require_premium", False):
        item.tags.append("Premium")
    if getattr(gift, "crafted", False):
        item.tags.append("Crafted")
    if getattr(gift, "resale_ton_only", False):
        item.tags.append("TON only")

    if item.is_rich:
        item.tags.append("💎 Rich")  # отображается в UI через bot_ui.ce()

    return item


def passes(cfg: dict, item: Listing) -> bool:
    """Проходит ли лот пользовательские фильтры (валюта + цена)."""
    if item.currency == "stars" and not cfg.get("cur_stars", True):
        return False
    if item.currency == "ton" and not cfg.get("cur_ton", True):
        return False

    if cfg.get("show_rich", False) and not item.is_rich:
        return False

    if cfg.get("require_username", False) and not item.owner_username:
        return False

    # пороги цены заданы в звёздах, поэтому к TON-лотам не применяются
    if item.currency == "stars":
        lo = float(cfg.get("min_price", 0) or 0)
        hi = float(cfg.get("max_price", 0) or 0)
        if lo and item.price < lo:
            return False
        if hi and item.price > hi:
            return False
    return True
