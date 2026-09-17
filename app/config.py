"""Хранение настроек и путей приложения."""
import json
import os
import sys
from pathlib import Path

APP_NAME = "TgGiftRadar"

CEO_ID = 7863407516

DEFAULTS = {
    "api_id": 0,
    "api_hash": "",
    "poll_interval": 20,        # пауза между полными кругами обхода, сек
    "request_delay": 0.6,       # пауза между запросами к API, сек
    "page_limit": 50,           # сколько лотов тянуть с первой страницы коллекции
    "only_active_resale": True, # обходить только коллекции, где сейчас есть резейл
    "show_existing_on_start": False,  # показать лоты, найденные при первом проходе
    "cur_stars": True,          # показывать лоты за звёзды
    "cur_ton": True,            # показывать лоты за TON
    "min_price": 0,             # фильтр по цене в звёздах (0 = выкл)
    "max_price": 0,
    "max_owner_gifts": 0,       # у владельца больше N обычных подарков -> скип (0 = выкл)
    "max_owner_nft": 0,         # у владельца больше N NFT -> скип (0 = выкл)
    "only_writable": False,     # показывать только тех, кому можно написать
    "only_russian": False,      # только русскоязычные продавцы
    "skip_hidden_owner": False, # резать лоты, где Telegram не показывает продавца
    "max_cards": 300,           # сколько карточек держать в ленте
    "sound": True,
    "collections": [],          # id выбранных коллекций
    "collections_set": False,   # False = список не трогали, берём все с резейлом
    "bot_token": "",            # токен от @BotFather (только для bot.py)
    "subscribers": [],          # chat_id тех, кто написал боту /start
    "ceo_id": CEO_ID,           # ID главного администратора (CEO)
    "subscriptions": {          # user_id -> {"expires_at": float|None, "role": "ceo"|"sub"}
        str(CEO_ID): {"expires_at": None, "role": "ceo"}
    },
    "group_settings": {         # настройки группы с темами
        "enabled": True,        # включена ли рассылка в группу
        "group_id": None,       # ID группы/супергруппы
        "topics": {},           # category_key -> topic_id (message_thread_id)
    },
    "disabled_categories": [],  # выключенные категории/темы лотов
    "accounts": [],             # список дополнительных аккаунтов для парсинга
}


def data_dir() -> Path:
    """Папка для сессии и настроек.

    В собранном .exe пишем в %APPDATA%, потому что папка рядом с exe
    может оказаться недоступной для записи (Program Files, флешка и т.п.).
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    else:
        base = Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


CONFIG_PATH = data_dir() / "config.json"
SESSION_PATH = data_dir() / "session"


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text("utf-8")))
        except Exception:
            pass
    # Гарантируем наличие CEO_ID в правах
    if "subscriptions" not in cfg:
        cfg["subscriptions"] = {}
    if str(CEO_ID) not in cfg["subscriptions"]:
        cfg["subscriptions"][str(CEO_ID)] = {"expires_at": None, "role": "ceo"}
    if "group_settings" not in cfg:
        cfg["group_settings"] = {"enabled": True, "group_id": None, "topics": {}}
    if "disabled_categories" not in cfg:
        cfg["disabled_categories"] = []
    if "accounts" not in cfg:
        cfg["accounts"] = []
    return cfg


def save(cfg: dict) -> None:
    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    tmp_path.replace(CONFIG_PATH)
