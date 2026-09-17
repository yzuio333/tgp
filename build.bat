@echo off
chcp 65001 >nul
echo === Gift Radar: сборка exe ===
python -m pip install -r requirements.txt
python -m PyInstaller gift_radar.spec --noconfirm --clean
echo.
echo Готово. Файл: dist\GiftRadar.exe
pause
