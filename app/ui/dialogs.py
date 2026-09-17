"""Диалоги: ключи API и пошаговый вход в Telegram."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ApiKeysDialog(QDialog):
    """Просит api_id / api_hash с my.telegram.org (нужно один раз)."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.demo = False
        self.setWindowTitle("Ключи Telegram API")
        self.setMinimumWidth(430)

        box = QVBoxLayout(self)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(10)

        head = QLabel("Подключение к Telegram API")
        head.setObjectName("CardTitle")
        box.addWidget(head)

        hint = QLabel(
            "Откройте my.telegram.org → API development tools,\n"
            "создайте приложение и вставьте сюда api_id и api_hash."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        box.addWidget(hint)

        link = QPushButton("Открыть my.telegram.org")
        link.setObjectName("Ghost")
        link.setCursor(Qt.PointingHandCursor)
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://my.telegram.org")))
        box.addWidget(link, 0, Qt.AlignLeft)

        self.id_edit = QLineEdit(str(cfg.get("api_id") or ""))
        self.id_edit.setPlaceholderText("api_id, например 1234567")
        self.hash_edit = QLineEdit(cfg.get("api_hash", ""))
        self.hash_edit.setPlaceholderText("api_hash, 32 символа")
        box.addWidget(self.id_edit)
        box.addWidget(self.hash_edit)

        self.err = QLabel("")
        self.err.setObjectName("Muted")
        box.addWidget(self.err)

        row = QHBoxLayout()
        demo_btn = QPushButton("Посмотреть демо")
        demo_btn.setObjectName("Ghost")
        demo_btn.setCursor(Qt.PointingHandCursor)
        demo_btn.setToolTip("Интерфейс с придуманными лотами, без подключения к Telegram")
        demo_btn.clicked.connect(self._demo)
        row.addWidget(demo_btn)
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Сохранить")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        box.addLayout(row)

    def _demo(self) -> None:
        self.demo = True
        self.accept()

    def _accept(self) -> None:
        raw_id = self.id_edit.text().strip()
        raw_hash = self.hash_edit.text().strip()
        if not raw_id.isdigit() or int(raw_id) <= 0:
            self.err.setText("api_id должен быть числом")
            return
        if len(raw_hash) < 30:
            self.err.setText("api_hash выглядит слишком коротким")
            return
        self.cfg["api_id"] = int(raw_id)
        self.cfg["api_hash"] = raw_hash
        self.accept()


class AskDialog(QDialog):
    """Один шаг входа: номер, код или облачный пароль."""

    def __init__(self, title: str, hint: str, placeholder: str,
                 secret: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.value: str | None = None

        box = QVBoxLayout(self)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(10)

        head = QLabel(title)
        head.setObjectName("CardTitle")
        box.addWidget(head)

        if hint.strip():
            lbl = QLabel(hint)
            lbl.setObjectName("Muted")
            lbl.setWordWrap(True)
            box.addWidget(lbl)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        if secret:
            self.edit.setEchoMode(QLineEdit.Password)
        self.edit.returnPressed.connect(self._accept)
        box.addWidget(self.edit)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Далее")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        box.addLayout(row)

    def _accept(self) -> None:
        text = self.edit.text().strip()
        if not text:
            return
        self.value = text
        self.accept()
