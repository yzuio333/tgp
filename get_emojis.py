import asyncio
from telethon import TelegramClient
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName
import json
import os

with open("data/config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

async def main():
    session_file = cfg.get("session_path", "data/default.session")
    if not os.path.exists(session_file):
        print("Session not found:", session_file)
        # Try to find any session
        for file in os.listdir("data"):
            if file.endswith(".session"):
                session_file = os.path.join("data", file)
                break
    
    print("Using session:", session_file)
    client = TelegramClient(session_file, int(cfg["api_id"]), cfg["api_hash"])
    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized!")
        return

    try:
        stickers = await client(GetStickerSetRequest(
            stickerset=InputStickerSetShortName(short_name="OutlineEmoji"),
            hash=0
        ))
        print(f"Found {len(stickers.documents)} emojis in OutlineEmoji:")
        for doc in stickers.documents:
            # The alt emoji character associated with it
            alt = "unknown"
            for attr in doc.attributes:
                if hasattr(attr, 'alt'):
                    alt = attr.alt
            print(f"Alt: {alt}, ID: {doc.id}")
    except Exception as e:
        print("Error:", e)
    await client.disconnect()

asyncio.run(main())
