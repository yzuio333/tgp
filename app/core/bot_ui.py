"""Клавиатуры и тексты меню телеграм-бота."""
import html
import re
import time
import urllib.parse

from telethon import Button
from telethon.tl.types import MessageEntityCustomEmoji

from .categories import CATEGORIES

PER_PAGE = 8
RULE = "━━━━━━━━━━━━━━━━━━━━"

# подписи кнопок нижней клавиатуры — по ним же ловим нажатия
KB_RUN = "Запустить"
KB_PAUSE = "Пауза"
KB_PANEL = "Панель"
KB_COLS = "Коллекции"
KB_PARAMS = "Параметры"
KB_OWNER = "Владелец"
KB_ADMIN = "Админка"

# ─── OutlineEmoji mapping ───────────────────────────────────
# Маркер: один Unicode-символ → document_id кастомного эмодзи из пака OutlineEmoji
_CUSTOM_EMOJI = {
    "🚀": 5372917041193828849,
    "🔥": 5289722755871162900,
    "⛔": 5332296662142434561,
    "👀": 5280881372418816002,
    "🎁": 5359664288241829619,
    "✈️": 5372849966689566579,
    "🔜": 5355075407743826720,
    "😎": 5289650686319929628,
    "🤖": 5355051922862653659,
    "😱": 5449701482964198097,
    "🧐": 5402461597237004802,
    "❤️": 5442678635909621223,
    "👍": 5458604417592863845,
    "💎": 5456384164313966322,  # 🤯 outline
    "⭐": 5289722755871162900,  # reuse 🔥 for star
    "🇷🇺": 5337037846475720165,  # 👾 outline (placeholder for flag)
    "👋": 5458904472598095631,
    "🧩": 5449875850046481967,  # 🤔 outline — атрибут модели
    "🎨": 5456149049214249060,  # 🥰 outline — атрибут фона
    "👤": 5458904472598095631,  # 👋 outline — продавец
    "🛰": 5372917041193828849,  # reuse 🚀 — заголовок help
    "🟢": 5397866377367268054,  # 😊 outline — активен
    "🔴": 5314766512605634930,  # 😡 outline — неактивен
    "⏸": 5289772607556568230,  # 😶 outline — пауза
    "👎": 5458772252029887718,
    "💔": 5445040416950856638,
    "👌": 5382026293166489702,
    "💯": 5206318837489743801,
    "🤡": 5299024976429466492,
    "👻": 5305388752162539722,
    "🌚": 5355313550795490720,
    "🗿": 5208878706717636743,
    "😭": 5458490510765206019,
    "🔙": 5352759161945867747,
    "➖": 5382026293166489702,
    "➕": 5206318837489743801,
    "🔄": 5355075407743826720,
    "🗑": 5332296662142434561,
    "◀️": 5352759161945867747,
    "▶️": 5372917041193828849,
    "📊": 5402461597237004802,
    "⚙️": 5449875850046481967,
    "✍️": 5458604417592863845,
}

# Символы-заглушки для вставки в текст.
def ce(char: str) -> str:
    """Оборачивает обычный эмодзи в тег <tg-emoji> если он есть в маппинге."""
    if char in _CUSTOM_EMOJI:
        return f'<tg-emoji emoji-id="{_CUSTOM_EMOJI[char]}">{char}</tg-emoji>'
    return char

E_ROCKET = ce("🚀")
E_FIRE = ce("🔥")
E_STOP = ce("⛔")
E_EYE = ce("👀")
E_GIFT = ce("🎁")
E_PLANE = ce("✈️")
E_SOON = ce("🔜")
E_COOL = ce("😎")
E_BOT = ce("🤖")
E_SCREAM = ce("😱")
E_HMM = ce("🧐")
E_HEART = ce("❤️")
E_LIKE = ce("👍")
E_PUZZLE = ce("🧩")
E_ART = ce("🎨")
E_USER = ce("👤")
E_SAT = ce("🛰")
E_GREEN = ce("🟢")
E_RED = ce("🔴")
E_PAUSE = ce("⏸")
E_STAR = ce("⭐")
E_GEM = ce("💎")
E_DISLIKE = ce("👎")
E_WAVE = ce("👋")



def tbtn(text, emoji=None, resize=True):
    icon = _CUSTOM_EMOJI.get(emoji) if emoji else None
    return Button.text(text, resize=resize, icon=icon)

def ibtn(text, data, emoji=None, style=None):
    icon = _CUSTOM_EMOJI.get(emoji) if emoji else None
    kwargs = {}
    if style: kwargs["style"] = style
    if icon: kwargs["icon"] = icon
    return Button.inline(text, data, **kwargs)

def _flag(on: bool) -> str:
    return ce("🟢") if on else ce("🔴")


def keyboard(scanning: bool, is_ceo: bool = False):
    """Постоянная клавиатура под полем ввода."""
    rows = [
        [tbtn(KB_PAUSE if scanning else KB_RUN, "⏸" if scanning else "▶️"),
         tbtn(KB_PANEL, "📊")],
        [tbtn(KB_COLS, "🎁"),
         tbtn(KB_PARAMS, "⚙️"),
         tbtn(KB_OWNER, "👤")],
    ]
    if is_ceo:
        rows.append([tbtn(KB_ADMIN, "⚙️")])
    return rows


def bar(done: int, total: int, width: int = 10) -> str:
    """Полоска прогресса из блоков."""
    if total <= 0:
        return "▱" * width
    filled = max(0, min(width, round(width * done / total)))
    return "▰" * filled + "▱" * (width - filled)


def ago(ts: float) -> str:
    """«3 мин назад» для метки времени."""
    if not ts:
        return "—"
    sec = int(time.time() - ts)
    if sec < 60:
        return f"{sec} сек назад"
    if sec < 3600:
        return f"{sec // 60} мин назад"
    if sec < 86400:
        return f"{sec // 3600} ч {sec % 3600 // 60} мин назад"
    return f"{sec // 86400} дн назад"


def uptime(started: float) -> str:
    sec = int(time.time() - started)
    if sec < 3600:
        return f"{sec // 60} мин"
    if sec < 86400:
        return f"{sec // 3600} ч {sec % 3600 // 60} мин"
    return f"{sec // 86400} дн {sec % 86400 // 3600} ч"


def filters_line(cfg: dict) -> str:
    """Компактная сводка фильтров лота."""
    cur = []
    if cfg.get("cur_stars", True):
        cur.append(ce("⭐"))
    if cfg.get("cur_ton", True):
        cur.append("TON")

    lo = int(cfg.get("min_price", 0) or 0)
    hi = int(cfg.get("max_price", 0) or 0)
    if lo and hi:
        price = f"{lo:,}–{hi:,}".replace(",", " ")
    elif lo:
        price = f"от {lo:,}".replace(",", " ")
    elif hi:
        price = f"до {hi:,}".replace(",", " ")
    else:
        price = "любая"
    return f"{'+'.join(cur) or '—'} · цена {price}"


def hud(cfg: dict, st: dict, is_ceo: bool = False):
    """Живая панель: состояние, прогресс круга и статистика."""
    scanning = st.get("scanning", False)
    dot = f"{E_FIRE} слежу" if scanning else f"{E_STOP} пауза"

    lines = [
        f"{E_ROCKET} <b>GIFT RADAR</b>",
        RULE,
        f"{dot}  ·  {E_EYE} {uptime(st.get('started', time.time()))}",
    ]

    total = st.get("cycle_n", 0)
    if scanning and total:
        done = st.get("cycle_i", 0)
        lines.append(
            f"<code>{bar(done, total)}</code> {done}/{total}"
            f"  ·  {html.escape(str(st.get('current', '')))[:22]}"
        )
    elif scanning:
        lines.append(f"<code>{bar(0, 1)}</code> готовлюсь к кругу")

    skipped = st.get("skip_owner", 0) + st.get("skip_filter", 0)
    lines += [
        "",
        f"{E_GIFT} найдено <b>{st.get('found', 0)}</b>"
        f"   {E_PLANE} отправлено <b>{st.get('sent', 0)}</b>",
        f"{E_STOP} отсеяно <b>{skipped}</b> <i>{skip_detail(st)}</i>",
        f"{E_EYE} последний лот: {ago(st.get('last_found', 0))}"
        f"   {E_SOON} кругов: {st.get('cycles', 0)}",
        RULE,
        f"{E_GIFT} коллекций <b>{st.get('targets', 0)}</b>  ·  {filters_line(cfg)}",
        owner_line(cfg).replace("Владелец: ", f"{E_COOL} "),
        f"{E_BOT} круг {cfg.get('poll_interval', 20)} сек · пауза {cfg.get('request_delay', 0.6)} сек"
        f" · лотов {cfg.get('page_limit', 50)}",
    ]

    warn = warnings(cfg, st)
    if warn:
        lines += [RULE] + warn

    buttons = [
        [ibtn("Пауза" if scanning else "Запустить", b"scan:toggle", "⏸" if scanning else "▶️", style="primary"),
         ibtn("Обновить", b"menu", "🔄", style="primary")],
        [ibtn("Коллекции", b"cols:0", "🎁", style="primary"),
         ibtn("Параметры", b"params", "⚙️", style="primary"),
         ibtn("Владелец", b"owner", "👤", style="primary")],
        [ibtn("Звёзды", b"cur:stars", "⭐", style="success" if cfg.get('cur_stars', True) else "danger"),
         ibtn("TON", b"cur:ton", "💎", style="success" if cfg.get('cur_ton', True) else "danger")],
    ]
    if is_ceo:
        buttons.append([ibtn("👑 Админка CEO", b"admin:menu", "⚙️", style="danger")])
    return "\n".join(lines), buttons


SKIP_NAMES = {
    "hidden": "продавец скрыт",
    "gifts": "много подарков",
    "nft": "много NFT",
    "write": "нельзя писать",
    "ru": "не русскоязычный",
}


def skip_detail(st: dict) -> str:
    """Расшифровка, из-за чего именно лоты не дошли."""
    parts = []
    for code, count in sorted((st.get("skip_by") or {}).items(),
                              key=lambda kv: -kv[1]):
        parts.append(f"{SKIP_NAMES.get(code, code)} {count}")
    if st.get("skip_filter"):
        parts.append(f"цена/валюта {st['skip_filter']}")
    return "(" + ", ".join(parts) + ")" if parts else ""


def warnings(cfg: dict, st: dict) -> list:
    """Почему сообщений может не быть — прямо в панели."""
    out = []
    if not st.get("subs"):
        out.append(f"{E_SCREAM} <b>никто не подписан</b> — нажмите /start, "
                   "иначе лоты некуда слать")
    if not st.get("targets"):
        out.append(f"{E_SCREAM} <b>не выбрано ни одной коллекции</b> — «{E_GIFT} Коллекции» → "
                   "«Все с резейлом»")
    if not st.get("scanning"):
        out.append(f"{E_SCREAM} слежение <b>на паузе</b> — нажмите «▶️ Запустить»")
    if not st.get("primed") and st.get("scanning") and st.get("targets"):
        out.append(f"{E_HMM} идёт первый круг: запоминаю рынок, сообщений пока не будет")
    if st.get("cycles") and not st.get("found") and st.get("skip_owner"):
        top = max((st.get("skip_by") or {}).items(), key=lambda kv: kv[1],
                  default=("", 0))[0]
        why = SKIP_NAMES.get(top, "фильтр владельца")
        out.append(f"{E_HMM} всё отсеивает «{why}» — ослабьте настройки в «{E_USER} Владелец»")
    return out


def owner_line(cfg: dict) -> str:
    """Однострочная сводка фильтров по владельцу для главного экрана."""
    parts = []
    gifts = int(cfg.get("max_owner_gifts", 0) or 0)
    nft = int(cfg.get("max_owner_nft", 0) or 0)
    if gifts:
        parts.append(f"подарков ≤ {gifts}")
    if nft:
        parts.append(f"NFT ≤ {nft}")
    if cfg.get("only_writable", False):
        parts.append("можно писать")
    if cfg.get("only_russian", False):
        parts.append(f"{ce('🇷🇺')} русскоязычные")
    return "Владелец: <b>" + (", ".join(parts) if parts else "без фильтра") + "</b>"


def params_menu(cfg: dict):
    """Числовые параметры с кнопками ±."""
    text = (
        f"{E_BOT} <b>Параметры</b>\n\n"
        f"Круг опроса: <b>{cfg.get('poll_interval', 20)} сек</b>\n"
        f"Пауза между запросами: <b>{cfg.get('request_delay', 0.6)} сек</b>\n"
        f"Лотов за запрос: <b>{cfg.get('page_limit', 50)}</b>\n"
        f"Цена от: <b>{int(cfg.get('min_price', 0) or 0)}</b> {ce('⭐')}\n"
        f"Цена до: <b>{int(cfg.get('max_price', 0) or 0) or '∞'}</b> {ce('⭐')}\n\n"
        f"{ce('👍') if cfg.get('show_existing_on_start', False) else ce('⛔')} показывать старые лоты\n"
        f"{ce('👍') if cfg.get('show_rich', False) else ce('⛔')} Показывать богатых (NFT, Black, <1000, 777...)\n\n"
        "<i>Точное значение: /set круг 30 · /set пауза 0.8 · /set лимит 100 · "
        "/set от 1000 · /set до 50000</i>"
    )
    buttons = [
        [ibtn("круг −5", b"num:interval:-5", "➖", style="primary"),
         ibtn("круг +5", b"num:interval:5", "➕", style="primary")],
        [ibtn("пауза −0.1", b"num:delay:-1", "➖", style="primary"),
         ibtn("пауза +0.1", b"num:delay:1", "➕", style="primary")],
        [ibtn("лимит −10", b"num:limit:-10", "➖", style="primary"),
         ibtn("лимит +10", b"num:limit:10", "➕", style="primary")],
        [ibtn("Старые лоты", b"existing", "👻", style="success" if cfg.get('show_existing_on_start', False) else "danger")],
        [ibtn("Богатые", b"rich", "😎", style="success" if cfg.get('show_rich', False) else "danger")],
        [ibtn("Забыть виденное", b"reset", "🗑", style="primary"),
         ibtn("Назад", b"menu", "◀️", style="primary")],
    ]
    return text, buttons


def owner_menu(cfg: dict):
    """Фильтры по продавцу."""
    gifts = int(cfg.get("max_owner_gifts", 0) or 0)
    nft = int(cfg.get("max_owner_nft", 0) or 0)
    text = (
        f"{E_COOL} <b>Фильтр по владельцу</b>\n\n"
        f"Обычных подарков не больше: <b>{gifts or 'без лимита'}</b>\n"
        f"NFT не больше: <b>{nft or 'без лимита'}</b>\n"
        f"{ce('👍') if cfg.get('only_writable', False) else ce('⛔')} только те, кому можно написать\n\n"
        "<i>Считаются подарки, видимые в профиле. Лоты со скрытым владельцем "
        "при включённом фильтре пропускаются.\n"
        "Точное значение: /set подарки 5 · /set нфт 5</i>"
    )
    buttons = [
        [ibtn("подарки −1", b"num:ogifts:-1", "➖", style="primary"),
         ibtn("подарки +1", b"num:ogifts:1", "➕", style="primary")],
        [ibtn("NFT −1", b"num:onft:-1", "➖", style="primary"),
         ibtn("NFT +1", b"num:onft:1", "➕", style="primary")],
        [ibtn("Можно написать", b"writable", "✍️", style="success" if cfg.get('only_writable', False) else "danger")],
        [ibtn("Русскоязычные", b"russian", "🇷🇺", style="success" if cfg.get('only_russian', False) else "danger")],
        [ibtn("Прятать скрытых", b"hidden", "🌚", style="success" if cfg.get('skip_hidden_owner', False) else "danger"),
         ibtn("Только с @", b"username", "🤖", style="success" if cfg.get('require_username', False) else "danger")],
        [ibtn("Сбросить лимиты", b"owner:clear", "🗑", style="primary"),
         ibtn("Назад", b"menu", "◀️", style="primary")],
    ]
    return text, buttons


def collections_page(items: list, chosen: set, page: int, query: str = ""):
    """Страница списка коллекций с галочками."""
    pool = items
    if query:
        pool = [c for c in items if query.lower() in c["title"].lower()]

    pages = max(1, (len(pool) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = pool[page * PER_PAGE:(page + 1) * PER_PAGE]

    head = f"{E_GIFT} <b>Коллекции</b> — выбрано {len(chosen)}"
    if query:
        head += f"\nфильтр: <code>{html.escape(query)}</code> ({len(pool)} шт.)"
    text = (head + "\n\nВ скобках — сколько лотов сейчас на резейле.\n"
            "<i>Поиск: /find pepe · сброс поиска: /find</i>")

    buttons = []
    for c in chunk:
        on = c["id"] in chosen
        title = c["title"][:28]
        buttons.append([ibtn(f"{title} ({c['resale']})", f"col:{c['id']}".encode(), "🎁", style="success" if on else "danger")])

    nav = []
    if page > 0:
        nav.append(ibtn("Назад", f"cols:{page - 1}".encode(), "◀️", style="primary"))
    nav.append(ibtn(f"{page + 1}/{pages}", b"noop", "🔄", style="primary"))
    if page < pages - 1:
        nav.append(ibtn("Вперед", f"cols:{page + 1}".encode(), "▶️", style="primary"))
    buttons.append(nav)

    buttons.append([ibtn("Все с резейлом", b"cols:all", "💯", style="primary"),
                    ibtn("Снять все", b"cols:none", "⛔", style="primary")])
    buttons.append([ibtn("Назад", b"menu", "◀️", style="primary")])
    return text, buttons


def guest_welcome():
    """Экран-визитка для обычного пользователя (без подписки)."""
    text = (
        "<b>Gift Tracker</b>\n\n"
        "Лоты NFT-подарков в реальном времени по темам ниже минимального рынка.\n\n"
        "Купить/продать NFT за рубли — у @tonswiza."
    )
    buttons = [
        [Button.inline("👤 Подписка", b"guest:sub")],
        [Button.inline("Партнёрка", b"guest:partner")],
        [Button.inline("Расширенные функции", b"guest:features")],
        [Button.inline("ℹ Информация", b"guest:info")],
        [
            Button.url("Поддержка ↗", "https://t.me/sahil_ui"),
            Button.inline("Парсер ↗", b"guest:parser"),
        ],
    ]
    return text, buttons


def admin_menu(cfg: dict):
    """Главная панель CEO."""
    grp_settings = cfg.get("group_settings", {})
    grp_enabled = grp_settings.get("enabled", True)
    group_id = grp_settings.get("group_id")
    subs = cfg.get("subscriptions", {})
    accs = cfg.get("accounts", [])
    dis_cats = len(cfg.get("disabled_categories", []))

    group_status = f"ID <code>{group_id}</code>" if group_id else "не привязана"
    text = (
        "👑 <b>Панель управления CEO</b>\n\n"
        f"• Супергруппа: <b>{group_status}</b>\n"
        f"• Отправка в группу: <b>{'🟢 ВКЛЮЧЕНА' if grp_enabled else '🔴 ВЫКЛЮЧЕНА'}</b>\n"
        f"• Подписчиков: <b>{len(subs)}</b>\n"
        f"• Доп. аккаунтов парсинга: <b>{len(accs)}</b>\n"
        f"• Отключено тем/категорий: <b>{dis_cats}</b>\n\n"
        "<i>Нажмите кнопку ниже для управления соответствующим разделом:</i>"
    )
    buttons = [
        [ibtn("Рассылка в группу: ВКЛ" if grp_enabled else "Рассылка в группу: ВЫКЛ",
              b"admin:toggle_group", "🟢" if grp_enabled else "🔴",
              style="success" if grp_enabled else "danger")],
        [ibtn("📂 Категории и топики", b"admin:cats", "📊", style="primary"),
         ibtn("🔑 Подписки", b"admin:subs", "👤", style="primary")],
        [ibtn("📱 Аккаунты парсера", b"admin:accs", "🤖", style="primary"),
         ibtn("🔄 Перезапустить бота", b"admin:restart", "🔄", style="danger")],
        [ibtn("◀️ Назад в меню", b"menu", "◀️", style="primary")],
    ]
    return text, buttons


def admin_categories_menu(cfg: dict):
    """Управление 11 темами форума и категориями."""
    disabled = set(cfg.get("disabled_categories", []))
    topics = cfg.get("group_settings", {}).get("topics", {})

    text = (
        "📂 <b>Категории и темы форума</b>\n\n"
        "Нажмите на категорию, чтобы включить/отключить её.\n"
        "<i>Для привязки топика супергруппы: напишите в нужной теме форума <code>/bind &lt;ключ&gt;</code></i>"
    )
    buttons = []
    for cat_key, cat_title in CATEGORIES.items():
        is_on = cat_key not in disabled
        topic_id = topics.get(cat_key)
        suffix = f" [топик #{topic_id}]" if topic_id else ""
        icon = "🟢" if is_on else "🔴"
        buttons.append([
            ibtn(f"{cat_title}{suffix}", f"admin:cat:{cat_key}".encode(), icon,
                 style="success" if is_on else "danger")
        ])

    buttons.append([ibtn("◀️ Назад в админку", b"admin:menu", "◀️", style="primary")])
    return text, buttons


def admin_subs_menu(cfg: dict):
    """Список подписок и команды управления."""
    subs = cfg.get("subscriptions", {})
    lines = ["🔑 <b>Управление подписками</b>\n"]
    for uid, info in subs.items():
        role = info.get("role", "sub")
        exp = info.get("expires_at")
        if role == "ceo":
            status = "👑 CEO (Бессрочно)"
        elif exp is None:
            status = "Бессрочно"
        else:
            diff = exp - time.time()
            if diff > 0:
                days = int(diff // 86400)
                hours = int((diff % 86400) // 3600)
                status = f"осталось {days}д {hours}ч"
            else:
                status = "истекла"
        lines.append(f"• <code>{uid}</code>: <b>{status}</b>")

    lines.append("\n<b>Команды:</b>")
    lines.append("<code>/sub &lt;user_id&gt; [дней]</code> — выдать подписку")
    lines.append("<i>Пример: <code>/sub 12345678 30</code> (или без числа для бессрочной)</i>")
    lines.append("<code>/unsub &lt;user_id&gt;</code> — отозвать подписку")
    buttons = [[ibtn("◀️ Назад в админку", b"admin:menu", "◀️", style="primary")]]
    return "\n".join(lines), buttons


def admin_accounts_menu(cfg: dict, active_count: int):
    """Список аккаунтов-парсеров."""
    accs = cfg.get("accounts", [])
    lines = [
        "📱 <b>Пул аккаунтов парсера</b>\n",
        f"Активных подключений: <b>{active_count}</b>\n",
        "• Основной аккаунт: <code>session_bot_user</code> (активен)",
    ]
    for idx, a in enumerate(accs):
        name = html.escape(str(a.get("name", "")))
        phone = a.get("phone", "")
        lines.append(f"• Доп. #{idx+1}: {name} (<code>{phone}</code>)")

    lines.append("\n<i>Нажмите «➕ Добавить аккаунт», чтобы подключить новый номер через Telegram.</i>")
    buttons = [
        [ibtn("➕ Добавить аккаунт", b"admin:add_acc", "➕", style="success")],
    ]
    if accs:
        buttons.append([ibtn("🗑 Очистить доп. аккаунты", b"admin:clear_accs", "🗑", style="danger")])
    buttons.append([ibtn("◀️ Назад в админку", b"admin:menu", "◀️", style="primary")])
    return "\n".join(lines), buttons
