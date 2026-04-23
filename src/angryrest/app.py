import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from angryrest.ui.main_window import MainWindow


def _load_stylesheet() -> str:
    qss_path = Path(__file__).parent / "resources" / "styles.qss"
    if qss_path.exists():
        content = qss_path.read_text(encoding="utf-8")
        resources_dir = str(qss_path.parent).replace("\\", "/")
        return content.replace("__RESOURCES__", resources_dir)
    return ""


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AngryREST")
    app.setOrganizationName("AngryREST")

    stylesheet = _load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
