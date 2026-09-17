# PyInstaller: сборка телеграм-бота Gift Radar (консольное окно)
# Собрать:  python -m PyInstaller gift_radar_bot.spec --noconfirm

block_cipher = None

a = Analysis(
    ["bot.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["telethon"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "PyQt5", "PyQt6", "tkinter",
              "matplotlib", "numpy", "pandas"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GiftRadarBot",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,           # нужен ввод телефона/кода при первом запуске
    icon="assets/icon.ico",
)
