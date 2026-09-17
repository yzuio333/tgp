"""Тёмная тема приложения: палитра + таблица стилей Qt."""

BG = "#0B0E14"
PANEL = "#111621"
CARD = "#151A26"
CARD_HOVER = "#1B2231"
BORDER = "#222A3A"
TEXT = "#E7ECF5"
MUTED = "#79839A"
ACCENT = "#6C8CFF"
ACCENT_DIM = "#3D56B5"
GREEN = "#25D0A3"
GOLD = "#FFC53D"
RED = "#FF6B6B"

LEVEL_COLORS = {"info": MUTED, "ok": GREEN, "warn": GOLD, "err": RED}

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QWidget#Root {{ background: {BG}; }}

QWidget#Sidebar {{ background: {PANEL}; }}
QScrollArea#SidebarScroll {{
    background: {PANEL};
    border: none;
    border-right: 1px solid {BORDER};
}}
QLabel#Logo {{ font-size: 19px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#LogoSub {{ font-size: 11px; color: {MUTED}; }}
QLabel#SectionTitle {{
    font-size: 11px; font-weight: 700; color: {MUTED};
    letter-spacing: 1.2px; padding-top: 6px;
}}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#StatBig {{ font-size: 26px; font-weight: 700; }}
QLabel#StatCaption {{ font-size: 11px; color: {MUTED}; }}

QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {CARD_HOVER}; border-color: #2E3850; }}
QPushButton:pressed {{ background: #10151F; }}
QPushButton:disabled {{ color: #4A5266; border-color: #1B2130; }}

QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {ACCENT}, stop:1 #8E6CFF);
    border: none; font-weight: 600; font-size: 14px; padding: 12px 16px;
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #7E9AFF, stop:1 #9E80FF);
}}
QPushButton#Danger {{ color: {RED}; }}
QPushButton#Danger:hover {{ background: #2A1620; border-color: #58202E; }}
QPushButton#Ghost {{ background: transparent; border-color: transparent; color: {MUTED}; }}
QPushButton#Ghost:hover {{ color: {TEXT}; background: {CARD}; }}

QPushButton#CardOpen {{
    background: transparent; border: 1px solid {BORDER};
    border-radius: 9px; padding: 7px 13px; color: {TEXT};
}}
QPushButton#CardOpen:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#CardDone {{
    background: transparent; border: 1px solid #23503F;
    border-radius: 9px; padding: 7px 13px; color: {GREEN}; font-weight: 600;
}}
QPushButton#CardDone:hover {{ background: #12301F; border-color: {GREEN}; }}

QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid #2E3850; background: {BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QListWidget {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{ padding: 5px 6px; border-radius: 7px; }}
QListWidget::item:hover {{ background: {CARD}; }}
QListWidget::item:selected {{ background: {CARD_HOVER}; color: {TEXT}; }}

QScrollArea {{ background: transparent; border: none; }}
QWidget#FeedHolder, QWidget#FeedViewport {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: #262F42; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: #33405A; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: #262F42; border-radius: 5px; min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{ background: #33405A; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#Card:hover {{ background: {CARD_HOVER}; border-color: #2E3850; }}
QLabel#CardTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#CardNum {{ font-size: 13px; color: {MUTED}; font-weight: 600; }}
QLabel#CardPrice {{ font-size: 17px; font-weight: 700; color: {GOLD}; }}
QLabel#CardMeta {{ font-size: 12px; color: {MUTED}; }}
QLabel#Tag {{
    font-size: 10px; font-weight: 700; color: {ACCENT};
    background: rgba(108, 140, 255, 0.12);
    border: 1px solid rgba(108, 140, 255, 0.35);
    border-radius: 7px; padding: 2px 7px;
}}
QLabel#Empty {{ font-size: 14px; color: {MUTED}; }}

QDialog {{ background: {PANEL}; }}
QToolTip {{
    background: {PANEL}; color: {TEXT};
    border: 1px solid {BORDER}; padding: 6px; border-radius: 6px;
}}
"""
