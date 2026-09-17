"""Чистые запросы к маркету, без Qt и без UI.

Используется и десктопным воркером, и телеграм-ботом.
"""
from telethon.tl import functions, types


async def catalog(client) -> list[dict]:
    """Список коллекций подарков: id, название, сколько сейчас на резейле."""
    res = await client(functions.payments.GetStarGiftsRequest(hash=0))
    items = []
    for g in getattr(res, "gifts", []):
        if not isinstance(g, types.StarGift):
            continue
        items.append({
            "id": g.id,
            "title": g.title or f"Gift {g.id}",
            "resale": g.availability_resale or 0,
            "total": g.availability_total or 0,
        })
    items.sort(key=lambda x: (-x["resale"], x["title"].lower()))
    return items


async def resale_page(client, gift_id: int, limit: int = 50) -> tuple[list, dict]:
    """Первая страница резейла коллекции: (лоты, владельцы по id).

    Флаги сортировки не передаём: Telegram отдаёт лоты в порядке
    выставления, свежие первыми — ровно то, что нужно для слежения.
    Пользователи из ответа несут access_hash, поэтому владельца можно
    опросить без отдельного resolve.
    """
    res = await client(functions.payments.GetResaleStarGiftsRequest(
        gift_id=gift_id, offset="", limit=limit,
    ))
    return res.gifts, {u.id: u for u in getattr(res, "users", [])}
