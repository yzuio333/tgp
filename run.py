"""Точка входа Gift Radar."""
import io
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app import config
from app.ui import theme
from app.ui.dialogs import ApiKeysDialog
from app.ui.main_window import MainWindow


def resource(name: str) -> Path:
    """Путь к ресурсу и в исходниках, и внутри собранного .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Gift Radar")
    app.setStyleSheet(theme.QSS)
    app.setFont(QFont("Segoe UI", 10))

    icon_path = resource("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    cfg = config.load()
    demo = "--demo" in sys.argv
    if not demo and (not cfg.get("api_id") or not cfg.get("api_hash")):
        dlg = ApiKeysDialog(cfg)
        if not dlg.exec():
            return 0
        demo = dlg.demo
        if not demo:
            config.save(cfg)

    win = MainWindow(cfg, demo=demo)
    win.show()
    return app.exec()


def _guard() -> int:
    """Окно собрано без консоли, поэтому пишем причину падения в файл."""
    # в windowed-сборке sys.stdout/stderr равны None: любой print внутри
    # библиотек уронил бы приложение молча
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

    try:
        return main()
    except Exception:                              # noqa: BLE001
        try:
            log = config.data_dir() / "crash.log"
            log.write_text(traceback.format_exc(), "utf-8")
        except Exception:                          # noqa: BLE001
            pass
        raise


if __name__ == "__main__":
    sys.exit(_guard())
