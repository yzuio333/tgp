"""Классификатор лотов по темам (топикам) форума супергруппы."""
import re
from typing import Optional

CATEGORIES = {
    "price_300_1000": "⚡ 300-1000",
    "arabic": "📺 арабы \\ израиль \\ иордания и т.д",
    "english": "✈️ англоязычные",
    "khabib": "Khabib's Papakha",
    "ufc": "UFC Strike",
    "black_backdrop": "💸 черный фон",
    "price_1000_5000": "⭐ 1000-5000",
    "price_5000_plus": "🔝 5000+",
    "expensive_models": "💎 дорогие модели",
    "girls": "🧕 девушки",
    "chinese": "✈️ китай",
}

ARABIC_COUNTRIES = {"AE", "SA", "IL", "JO", "EG", "IQ", "KW", "QA", "OM", "BH", "LB", "SY", "PS", "YE"}
ENGLISH_COUNTRIES = {"US", "GB", "CA", "AU", "NZ", "IE"}
CHINESE_COUNTRIES = {"CN", "HK", "TW", "SG"}
GIRL_MARKERS = ["girl", "woman", "queen", "princess", "lady", "девушка", "тян", "милашка", "модель", "девочка", "miss", "mrs"]


def classify(item, owner_info=None, user_obj=None) -> list[str]:
    """Возвращает список ключей категорий, к которым относится данный лот."""
    matched = []

    # 1. Диапазоны цен (в звёздах или эквиваленте)
    if item.currency == "stars":
        if 300 <= item.price <= 1000:
            matched.append("price_300_1000")
        elif 1000 < item.price <= 5000:
            matched.append("price_1000_5000")
        elif item.price > 5000:
            matched.append("price_5000_plus")
    elif item.currency == "ton":
        stars_est = item.price * 200
        if 300 <= stars_est <= 1000:
            matched.append("price_300_1000")
        elif 1000 < stars_est <= 5000:
            matched.append("price_1000_5000")
        elif stars_est > 5000:
            matched.append("price_5000_plus")

    # 2. Коллекции
    title_low = (item.title or "").lower()
    col_low = (item.collection or "").lower()
    if "khabib" in title_low or "papakha" in title_low or "khabib" in col_low:
        matched.append("khabib")
    if "ufc" in title_low or "ufc" in col_low:
        matched.append("ufc")

    # 3. Черный фон
    backdrop_low = (item.backdrop or "").lower()
    if "black" in backdrop_low or "черн" in backdrop_low:
        matched.append("black_backdrop")

    # 4. Дорогие модели
    if item.model_rarity and item.model_rarity <= 50:
        matched.append("expensive_models")
    elif item.value_usd_amount > 3000 or item.is_rich:
        matched.append("expensive_models")

    # 5. География и язык продавца
    country = ""
    about = ""
    lang = ""
    if owner_info and hasattr(owner_info, "country"):
        country = (owner_info.country or "").upper()
        about = (getattr(owner_info, "about", "") or "").lower()
        lang = (getattr(owner_info, "lang", "") or "").lower()
    elif user_obj:
        lang = (getattr(user_obj, "lang_code", "") or "").lower()

    text_check = f"{item.owner} {item.owner_username} {about}".lower()

    if country in ARABIC_COUNTRIES or re.search(r"[\u0600-\u06FF\u0590-\u05FF]", text_check):
        matched.append("arabic")

    if country in ENGLISH_COUNTRIES or lang.startswith("en"):
        matched.append("english")

    if country in CHINESE_COUNTRIES or lang.startswith("zh") or re.search(r"[\u4e00-\u9fff]", text_check):
        matched.append("chinese")

    if any(m in text_check for m in GIRL_MARKERS):
        matched.append("girls")

    return matched
