import asyncio
import json
from aiogram import Bot

async def main():
    with open('data/config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    bot = Bot(token=cfg['bot_token'])
    chat_id = 8152013826
    
    text = 'Test aiogram: <tg-emoji emoji-id="5372917041193828849">🚀</tg-emoji>'
    
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        print("Message sent via aiogram!")
    except Exception as e:
        print("ERROR:", e)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
