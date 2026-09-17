import asyncio
import json
from telethon import TelegramClient
from telethon.tl.types import MessageEntityCustomEmoji

EMOJI_MAPPING = {
    "🚀": 5372917041193828849,
    "🔥": 5289722755871162900
}

class EmojiFormatter:
    @staticmethod
    def prepare_message(text: str, mapping: dict):
        entities = []
        for emoji_char, doc_id in mapping.items():
            start_pos = 0
            while True:
                pos = text.find(emoji_char, start_pos)
                if pos == -1: break
                offset = len(text[:pos].encode('utf-16-le')) // 2
                length = len(emoji_char.encode('utf-16-le')) // 2
                entities.append(MessageEntityCustomEmoji(offset=offset, length=length, document_id=doc_id))
                start_pos = pos + len(emoji_char)
        entities.sort(key=lambda e: e.offset)
        return text, entities

async def main():
    with open("data/config.json", "r", encoding="utf-8") as f: cfg = json.load(f)
    bot = TelegramClient("data/session_bot.session", int(cfg["api_id"]), cfg["api_hash"])
    await bot.start(bot_token=cfg["bot_token"])
    text, entities = EmojiFormatter.prepare_message("Test EmojiFormatter: 🚀 🔥", EMOJI_MAPPING)
    try:
        await bot.send_message(8152013826, text, formatting_entities=entities)
        print("Sent via bot MTProto with sorting!")
    except Exception as e:
        print("ERROR:", e)
    await bot.disconnect()

asyncio.run(main())
