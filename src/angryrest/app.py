from __future__ import annotations

import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from angryrest.ui.bootstrap import bootstrap_engine


def main() -> None:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("AngryREST")
    app.setOrganizationName("AngryREST")

    engine = QQmlApplicationEngine()
    _collections_vm, _collection_service = bootstrap_engine(engine)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()