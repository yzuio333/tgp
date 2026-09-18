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

# Если лот подходит сразу под несколько тем, отправляем его только в одну.
# Специальные темы важнее общих ценовых диапазонов; цена остаётся запасным
# маршрутом, если для более специфичной темы нет привязанного топика.
CATEGORY_PRIORITY = (
    "khabib",
    "ufc",
    "black_backdrop",
    "arabic",
    "english",
    "chinese",
    "girls",
    "expensive_models",
    "price_5000_plus",
    "price_1000_5000",
    "price_300_1000",
)

ARABIC_COUNTRIES = {"AE", "SA", "IL", "JO", "EG", "IQ", "KW", "QA", "OM", "BH", "LB", "SY", "PS", "YE"}
ENGLISH_COUNTRIES = {"US", "GB", "CA", "AU", "NZ", "IE"}
CHINESE_COUNTRIES = {"CN", "HK", "TW", "SG"}
FEMALE_MARKERS = (
    "girl", "woman", "queen", "princess", "lady", "miss", "mrs",
    "девушка", "девочка", "тян", "милашка", "модель", "красотка",
    "принцесса", "мадемуазель",
)
FEMALE_NAMES = {
    # Частые русские имена и их распространённые варианты в username.
    "анна", "anna", "аня", "anya", "анюта",
    "мария", "maria", "маша", "masha", "маруся",
    "ольга", "olga", "оля",
    "елена", "elena", "лена", "lena",
    "ирина", "irina", "ира", "ira",
    "наталья", "natalia", "natalya", "наташа", "natasha",
    "светлана", "svetlana", "света", "sveta",
    "екатерина", "ekaterina", "katerina", "катя", "katya",
    "дарья", "daria", "darya", "даша", "dasha",
    "александра", "alexandra", "саша", "sasha",
    "анастасия", "anastasia", "настя", "nastya",
    "виктория", "victoria", "вика", "vika",
    "юлия", "yulia", "julia", "юля", "yulya",
    "ксения", "ksenia", "xenia", "ксюша", "ksusha",
    "полина", "polina", "соня", "sonya", "софия", "sofia",
    "марина", "marina", "карина", "karina", "алина", "alina",
    "вероника", "veronika", "валерия", "valeria", "вера", "vera",
    "лиза", "liza", "елизавета", "elizaveta", "яна", "yana",
    "людмила", "lyudmila", "любовь", "lubov", "зоя", "zoya",
    "тамара", "tamara", "варвара", "varvara", "милана", "milana",
    "олеся", "olesya", "надежда", "nadezhda", "галина", "galina",
}


def _topic_normalize(text: str) -> str:
    """Убирает эмодзи и пунктуацию для сопоставления названий топиков."""
    return re.sub(r"[^a-zа-яё0-9]+", "", (text or "").lower())


def topic_key(title: str) -> Optional[str]:
    """Определяет категорию по заголовку топика форума.

    Поддерживает названия из CATEGORIES и короткие варианты вроде
    ``300-1000`` или ``5000+`` со скриншота группы.
    """
    normalized = _topic_normalize(title)
    if not normalized:
        return None

    candidates_by_key = {
        key: {
            _topic_normalize(label),
            _topic_normalize(key.replace("_", " ")),
        }
        for key, label in CATEGORIES.items()
    }

    # Сначала точное совпадение. Это важно для ``5000+``: его нормализованная
    # форма ``5000`` одновременно является частью диапазона ``1000-5000``.
    for key, candidates in candidates_by_key.items():
        if normalized in candidates:
            return key

    for key, candidates in candidates_by_key.items():
        if any(candidate and (normalized in candidate or candidate in normalized)
               for candidate in candidates):
            return key
    return None


def primary_category(matched: list[str], disabled: set[str] | None = None,
                     topics: dict | None = None) -> Optional[str]:
    """Выбирает один маршрут с учётом приоритета и доступных топиков."""
    disabled = disabled or set()
    for key in CATEGORY_PRIORITY:
        if key not in matched or key in disabled:
            continue
        if topics is not None and not topics.get(key):
            continue
        return key
    return None


def _profile_tokens(*parts: str) -> list[str]:
    text = " ".join(p for p in parts if p)
    return re.findall(r"[a-zа-яё]+", text.lower())


def _looks_female(item, owner_info=None, user_obj=None) -> bool:
    """Эвристика по имени, username и описанию профиля.

    Telegram не передаёт признак пола и не сообщает пол по фотографии, поэтому
    аватар намеренно не используется: его распознавание потребовало бы скачивать
    личные изображения и дало бы много ложных срабатываний.
    """
    first = getattr(user_obj, "first_name", "") if user_obj else ""
    last = getattr(user_obj, "last_name", "") if user_obj else ""
    username = getattr(user_obj, "username", "") if user_obj else ""
    about = getattr(owner_info, "about", "") if owner_info else ""
    tokens = _profile_tokens(
        first, last, username, about,
        getattr(item, "owner", ""), getattr(item, "owner_username", ""),
    )
    if any(token in FEMALE_NAMES for token in tokens):
        return True
    return any(
        token == marker or token.startswith(marker)
        for token in tokens for marker in FEMALE_MARKERS
    )


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
        country = (getattr(user_obj, "phone_country", "") or "").upper()
        lang = (getattr(user_obj, "lang_code", "") or "").lower()

    visible_owner = bool(user_obj or (owner_info and owner_info.known)
                         or getattr(item, "owner_id", 0))
    text_check = " ".join([
        f"{item.owner} {item.owner_username}",
        about,
        getattr(user_obj, "first_name", "") if user_obj else "",
        getattr(user_obj, "last_name", "") if user_obj else "",
        getattr(user_obj, "username", "") if user_obj else "",
    ]).lower()

    if visible_owner and (country in ARABIC_COUNTRIES
                          or re.search(r"[\u0600-\u06FF\u0590-\u05FF]", text_check)):
        matched.append("arabic")

    if visible_owner and (country in ENGLISH_COUNTRIES or lang.startswith("en")):
        matched.append("english")

    if visible_owner and (country in CHINESE_COUNTRIES or lang.startswith("zh")
                          or re.search(r"[\u4e00-\u9fff]", text_check)):
        matched.append("chinese")

    if visible_owner and _looks_female(item, owner_info, user_obj):
        matched.append("girls")

    return matched
