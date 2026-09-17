import json
import urllib.request

with open('data/config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

token = cfg['bot_token']
chat_id = 8152013826

data = json.dumps({
    'chat_id': chat_id,
    'text': 'Test: <tg-emoji emoji-id="5372917041193828849">🚀</tg-emoji>',
    'parse_mode': 'HTML'
}).encode('utf-8')

req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data, headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print(json.loads(res.read()))
except Exception as e:
    print('ERROR:', e.read())
