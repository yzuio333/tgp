import asyncio
from telethon import TelegramClient
from telethon.tl.types import MessageEntityCustomEmoji
import json

async def main():
    with open('data/config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    # Подключаемся как ЮЗЕРБОТ (sahil)
    session_file = cfg.get("session_path", "data/default.session")
    client = TelegramClient(session_file, int(cfg["api_id"]), cfg["api_hash"])
    await client.connect()
    
    text = '🚀 GIFT RADAR'
    ents = [MessageEntityCustomEmoji(offset=0, length=2, document_id=5372917041193828849)]
    
    try:
        # Отправляем сообщение самому себе (в Избранное)
        await client.send_message('me', text, formatting_entities=ents)
        print("Отправлено от лица юзербота!")
    except Exception as e:
        print("ERROR:", e)

    await client.disconnect()

asyncio.run(main())
