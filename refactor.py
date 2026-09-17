import re

with open("app/core/bot_ui.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update KB_ constants
code = code.replace('KB_RUN = "▶️ Запустить"', 'KB_RUN = "Запустить"')
code = code.replace('KB_PAUSE = "⏸ Пауза"', 'KB_PAUSE = "Пауза"')
code = code.replace('KB_PANEL = "📊 Панель"', 'KB_PANEL = "Панель"')
code = code.replace('KB_COLS = "🎁 Коллекции"', 'KB_COLS = "Коллекции"')
code = code.replace('KB_PARAMS = "⚙️ Параметры"', 'KB_PARAMS = "Параметры"')
code = code.replace('KB_OWNER = "👤 Владелец"', 'KB_OWNER = "Владелец"')

# 2. Add new emojis to _CUSTOM_EMOJI
new_emojis = """    "➖": 5382026293166489702,
    "➕": 5206318837489743801,
    "🔄": 5355075407743826720,
    "🗑": 5332296662142434561,
    "◀️": 5352759161945867747,
    "▶️": 5372917041193828849,
    "📊": 5402461597237004802,
    "⚙️": 5449875850046481967,
    "✍️": 5458604417592863845,
"""
code = code.replace('    "🔙": 5352759161945867747,\n}', f'    "🔙": 5352759161945867747,\n{new_emojis}}}')

# 3. Add tbtn and ibtn helpers
helpers = """
def tbtn(text, emoji=None, resize=True):
    icon = _CUSTOM_EMOJI.get(emoji) if emoji else None
    return Button.text(text, resize=resize, icon=icon)

def ibtn(text, data, emoji=None, style=None):
    icon = _CUSTOM_EMOJI.get(emoji) if emoji else None
    kwargs = {}
    if style: kwargs["style"] = style
    if icon: kwargs["icon"] = icon
    return Button.inline(text, data, **kwargs)
"""
code = code.replace('def _flag(on: bool) -> str:', helpers + '\ndef _flag(on: bool) -> str:')

# 4. Replace keyboard
old_kb = """def keyboard(scanning: bool):
    \"\"\"Постоянная клавиатура под полем ввода.\"\"\"
    return [
        [Button.text(KB_PAUSE if scanning else KB_RUN, resize=True),
         Button.text(KB_PANEL, resize=True)],
        [Button.text(KB_COLS, resize=True),
         Button.text(KB_PARAMS, resize=True),
         Button.text(KB_OWNER, resize=True)],
    ]"""

new_kb = """def keyboard(scanning: bool):
    \"\"\"Постоянная клавиатура под полем ввода.\"\"\"
    return [
        [tbtn(KB_PAUSE if scanning else KB_RUN, "⏸" if scanning else "▶️"),
         tbtn(KB_PANEL, "📊")],
        [tbtn(KB_COLS, "🎁"),
         tbtn(KB_PARAMS, "⚙️"),
         tbtn(KB_OWNER, "👤")],
    ]"""
code = code.replace(old_kb, new_kb)

# 5. Replace inline buttons
code = code.replace('Button.inline("Пауза" if scanning else "Запустить", b"scan:toggle", style="primary")', 'ibtn("Пауза" if scanning else "Запустить", b"scan:toggle", "⏸" if scanning else "▶️", style="primary")')
code = code.replace('Button.inline("Обновить", b"menu", style="primary")', 'ibtn("Обновить", b"menu", "🔄", style="primary")')
code = code.replace('Button.inline("Коллекции", b"cols:0", style="primary")', 'ibtn("Коллекции", b"cols:0", "🎁", style="primary")')
code = code.replace('Button.inline("Параметры", b"params", style="primary")', 'ibtn("Параметры", b"params", "⚙️", style="primary")')
code = code.replace('Button.inline("Владелец", b"owner", style="primary")', 'ibtn("Владелец", b"owner", "👤", style="primary")')
code = code.replace('Button.inline("звёзды", b"cur:stars",', 'ibtn("Звёзды", b"cur:stars", "⭐",')
code = code.replace('Button.inline("TON", b"cur:ton",', 'ibtn("TON", b"cur:ton", "💎",')

code = code.replace('Button.inline("круг −5", b"num:interval:-5", style="primary")', 'ibtn("круг −5", b"num:interval:-5", "➖", style="primary")')
code = code.replace('Button.inline("круг +5", b"num:interval:5", style="primary")', 'ibtn("круг +5", b"num:interval:5", "➕", style="primary")')
code = code.replace('Button.inline("пауза −0.1", b"num:delay:-1", style="primary")', 'ibtn("пауза −0.1", b"num:delay:-1", "➖", style="primary")')
code = code.replace('Button.inline("пауза +0.1", b"num:delay:1", style="primary")', 'ibtn("пауза +0.1", b"num:delay:1", "➕", style="primary")')
code = code.replace('Button.inline("лимит −10", b"num:limit:-10", style="primary")', 'ibtn("лимит −10", b"num:limit:-10", "➖", style="primary")')
code = code.replace('Button.inline("лимит +10", b"num:limit:10", style="primary")', 'ibtn("лимит +10", b"num:limit:10", "➕", style="primary")')

code = code.replace('Button.inline("старые лоты",\n                       b"existing",', 'ibtn("Старые лоты", b"existing", "👻",')
code = code.replace('Button.inline("Показывать богатых",\n                       b"rich",', 'ibtn("Богатые", b"rich", "😎",')
code = code.replace('Button.inline("Забыть виденное", b"reset", style="primary")', 'ibtn("Забыть виденное", b"reset", "🗑", style="primary")')
code = code.replace('Button.inline("‹ Назад", b"menu", style="primary")', 'ibtn("Назад", b"menu", "◀️", style="primary")')

code = code.replace('Button.inline("подарки −1", b"num:ogifts:-1", style="primary")', 'ibtn("подарки −1", b"num:ogifts:-1", "➖", style="primary")')
code = code.replace('Button.inline("подарки +1", b"num:ogifts:1", style="primary")', 'ibtn("подарки +1", b"num:ogifts:1", "➕", style="primary")')
code = code.replace('Button.inline("NFT −1", b"num:onft:-1", style="primary")', 'ibtn("NFT −1", b"num:onft:-1", "➖", style="primary")')
code = code.replace('Button.inline("NFT +1", b"num:onft:1", style="primary")', 'ibtn("NFT +1", b"num:onft:1", "➕", style="primary")')

code = code.replace('Button.inline("Можно написать",\n                       b"writable",', 'ibtn("Можно написать", b"writable", "✍️",')
code = code.replace('Button.inline("Русскоязычные",\n                       b"russian",', 'ibtn("Русскоязычные", b"russian", "🇷🇺",')
code = code.replace('Button.inline("Прятать скрытых",\n                       b"hidden",', 'ibtn("Прятать скрытых", b"hidden", "🌚",')
code = code.replace('Button.inline("Только с @",\n                       b"username",', 'ibtn("Только с @", b"username", "🤖",')
code = code.replace('Button.inline("Сбросить лимиты", b"owner:clear", style="primary")', 'ibtn("Сбросить лимиты", b"owner:clear", "🗑", style="primary")')

code = code.replace('Button.inline(f"{title} ({c[\'resale\']})",\n                                      f"col:{c[\'id\']}".encode(),', 'ibtn(f"{title} ({c[\'resale\']})", f"col:{c[\'id\']}".encode(), "🎁",')
code = code.replace('Button.inline("‹ Назад", f"cols:{page - 1}".encode(), style="primary")', 'ibtn("Назад", f"cols:{page - 1}".encode(), "◀️", style="primary")')
code = code.replace('Button.inline(f"{page + 1}/{pages}", b"noop", style="primary")', 'ibtn(f"{page + 1}/{pages}", b"noop", "🔄", style="primary")')
code = code.replace('Button.inline("Вперед ›", f"cols:{page + 1}".encode(), style="primary")', 'ibtn("Вперед", f"cols:{page + 1}".encode(), "▶️", style="primary")')

code = code.replace('Button.inline("Все с резейлом", b"cols:all", style="primary")', 'ibtn("Все с резейлом", b"cols:all", "💯", style="primary")')
code = code.replace('Button.inline("Снять все", b"cols:none", style="primary")', 'ibtn("Снять все", b"cols:none", "⛔", style="primary")')

# Also fix the one in models.py button(item)
# Wait, models.py button(item) is in bot_runner.py!
# Ah, `def buttons(item)` is in bot_runner.py!
# We can fix that directly in bot_runner.py.

with open("app/core/bot_ui.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Done bot_ui.py")
