import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio
import json
from telethon import TelegramClient, Button

with open("data/config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

async def main():
    bot = TelegramClient("data/session_bot", int(cfg["api_id"]), cfg["api_hash"])
    await bot.start(bot_token=cfg["bot_token"])

    chat_id = cfg["subscribers"][0]

    inline_kb = [
        [Button.inline("Test Inline", b"test", icon=5372917041193828849)]
    ]
    reply_kb = [
        [Button.text("Test Reply", icon=5372917041193828849)]
    ]

    try:
        await bot.send_message(chat_id, "Inline KB:", buttons=inline_kb)
        print("Inline KB sent!")
    except Exception as e:
        print("Inline Error:", e)

    try:
        await bot.send_message(chat_id, "Reply KB:", buttons=reply_kb)
        print("Reply KB sent!")
    except Exception as e:
        print("Reply Error:", e)

    await bot.disconnect()

asyncio.run(main())
