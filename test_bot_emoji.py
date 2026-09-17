import asyncio
import json
import requests

with open('data/config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

token = cfg['bot_token']
res = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
updates = res.json().get('result', [])
if not updates:
    print("No updates found.")
else:
    for u in reversed(updates):
        if 'message' in u:
            chat_id = u['message']['chat']['id']
            break
        elif 'callback_query' in u:
            chat_id = u['callback_query']['message']['chat']['id']
            break
    else:
        chat_id = None
        
    if chat_id:
        print("Sending to chat_id:", chat_id)
        text = 'Test: <tg-emoji emoji-id="5442678635909621223">❤️</tg-emoji>'
        res = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })
        print(res.json())
