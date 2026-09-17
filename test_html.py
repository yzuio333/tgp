from telethon.extensions import html
text, ents = html.parse('Test: <tg-emoji emoji-id="123">X</tg-emoji>')
print(repr(text))
for e in ents:
    print(type(e), getattr(e, 'document_id', 'N/A'))
