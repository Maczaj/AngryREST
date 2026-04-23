from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from angryrest.models.environment import Environment


class EnvironmentDialog(QDialog):
    environments_changed = Signal()

    def __init__(
        self, environments: list[Environment], parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.environments = environments
        self.setWindowTitle("Manage Environments")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # Left: environment list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ New")
        add_btn.clicked.connect(self._add_environment)
        btn_layout.addWidget(add_btn)
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self._rename_environment)
        btn_layout.addWidget(rename_btn)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_environment)
        btn_layout.addWidget(del_btn)
        left_layout.addLayout(btn_layout)

        self.env_list = QListWidget()
        self.env_list.currentRowChanged.connect(self._on_env_selected)
        left_layout.addWidget(self.env_list)
        splitter.addWidget(left)

        # Right: variables table for selected environment
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("Variables"))

        self.vars_table = QTableWidget(0, 2)
        self.vars_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.vars_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.vars_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.vars_table.verticalHeader().setVisible(False)
        self.vars_table.cellChanged.connect(self._on_var_changed)
        right_layout.addWidget(self.vars_table)

        vars_btn_layout = QHBoxLayout()
        add_var_btn = QPushButton("+ Add Variable")
        add_var_btn.clicked.connect(self._add_variable)
        vars_btn_layout.addWidget(add_var_btn)
        del_var_btn = QPushButton("Remove Selected")
        del_var_btn.clicked.connect(self._delete_variable)
        vars_btn_layout.addWidget(del_var_btn)
        right_layout.addLayout(vars_btn_layout)

        splitter.addWidget(right)
        splitter.setSizes([200, 500])
        layout.addWidget(splitter)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._populate_env_list()

    def _populate_env_list(self) -> None:
        self.env_list.clear()
        for env in self.environments:
            self.env_list.addItem(env.name)
        if self.environments:
            self.env_list.setCurrentRow(0)

    def _on_env_selected(self, row: int) -> None:
        self.vars_table.blockSignals(True)
        self.vars_table.setRowCount(0)
        if 0 <= row < len(self.environments):
            env = self.environments[row]
            for key, value in env.variables.items():
                r = self.vars_table.rowCount()
                self.vars_table.insertRow(r)
                self.vars_table.setItem(r, 0, QTableWidgetItem(key))
                self.vars_table.setItem(r, 1, QTableWidgetItem(value))
        self.vars_table.blockSignals(False)

    def _on_var_changed(self, row: int, col: int) -> None:
        env_row = self.env_list.currentRow()
        if env_row < 0 or env_row >= len(self.environments):
            return
        env = self.environments[env_row]

        # Rebuild variables from table
        env.variables.clear()
        for r in range(self.vars_table.rowCount()):
            key_item = self.vars_table.item(r, 0)
            val_item = self.vars_table.item(r, 1)
            if key_item and key_item.text().strip():
                env.variables[key_item.text().strip()] = (
                    val_item.text() if val_item else ""
                )
        self.environments_changed.emit()

    def _add_variable(self) -> None:
        env_row = self.env_list.currentRow()
        if env_row < 0:
            return
        r = self.vars_table.rowCount()
        self.vars_table.insertRow(r)
        self.vars_table.setItem(r, 0, QTableWidgetItem(""))
        self.vars_table.setItem(r, 1, QTableWidgetItem(""))
        self.vars_table.editItem(self.vars_table.item(r, 0))

    def _delete_variable(self) -> None:
        row = self.vars_table.currentRow()
        if row >= 0:
            self.vars_table.removeRow(row)
            self._on_var_changed(0, 0)  # trigger save

    def _add_environment(self) -> None:
        name, ok = QInputDialog.getText(self, "New Environment", "Environment name:")
        if ok and name.strip():
            env = Environment(name=name.strip())
            self.environments.append(env)
            self._populate_env_list()
            self.env_list.setCurrentRow(len(self.environments) - 1)
            self.environments_changed.emit()

    def _rename_environment(self) -> None:
        row = self.env_list.currentRow()
        if row < 0:
            return
        env = self.environments[row]
        name, ok = QInputDialog.getText(
            self, "Rename Environment", "Name:", text=env.name
        )
        if ok and name.strip():
            env.name = name.strip()
            self.env_list.item(row).setText(env.name)
            self.environments_changed.emit()

    def _delete_environment(self) -> None:
        row = self.env_list.currentRow()
        if row < 0:
            return
        env = self.environments[row]
        reply = QMessageBox.question(
            self,
            "Delete Environment",
            f"Delete environment '{env.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.environments.remove(env)
            self._populate_env_list()
            self.environments_changed.emit()
