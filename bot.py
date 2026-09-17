"""Точка входа телеграм-бота Gift Radar (консольное приложение)."""
import asyncio
import sys

from app import config
from app.core.bot_runner import GiftBot


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)


def ensure_keys(cfg: dict) -> None:
    """Спросить всё, чего не хватает, и сохранить."""
    changed = False

    if not cfg.get("api_id") or not cfg.get("api_hash"):
        print("Нужны ключи с my.telegram.org (API development tools).")
        while True:
            raw = ask("api_id: ")
            if raw.isdigit() and int(raw) > 0:
                cfg["api_id"] = int(raw)
                break
            print("  api_id — это число.")
        while True:
            raw = ask("api_hash: ")
            if len(raw) >= 30:
                cfg["api_hash"] = raw
                break
            print("  api_hash — 32 символа.")
        changed = True

    if not cfg.get("bot_token"):
        print("\nТокен бота: откройте @BotFather → /newbot → скопируйте токен.")
        while True:
            raw = ask("bot_token: ")
            if ":" in raw and len(raw) > 20:
                cfg["bot_token"] = raw
                break
            print("  Токен выглядит как 1234567890:AAH...")
        changed = True

    if changed:
        config.save(cfg)


def main() -> int:
    print("=== Gift Radar Bot ===")
    cfg = config.load()
    ensure_keys(cfg)

    bot = GiftBot(cfg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        print("\nОстановка, отправка уведомлений...")
        loop.run_until_complete(bot.shutdown_message())
    except Exception as e:                      # noqa: BLE001
        print(f"\nОшибка: {e}")
        ask("Enter — закрыть...")
        return 1
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
