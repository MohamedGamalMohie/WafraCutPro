"""
Remnants and Usable Offcuts Inventory View
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QMessageBox
)
from PyQt6.QtCore import Qt

from steel_nest.database.repositories import RemnantRepository
from steel_nest.config import RemnantStatus

class RemnantsView(QWidget):
    def __init__(self, remnant_repo: RemnantRepository, parent=None):
        super().__init__(parent)
        self.remnant_repo = remnant_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        h_title = QLabel("Remnants & Reusable Offcuts Inventory")
        h_title.setObjectName("viewTitle")
        h_sub = QLabel("Track, reserve, and reuse left-over stock lengths and plate remnants from production runs.")
        h_sub.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_box.addLayout(title_box)
        h_box.addStretch()

        # Filter combo
        lbl_f = QLabel("Filter Status:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Statuses", None)
        self.filter_combo.addItem("Reusable", RemnantStatus.REUSABLE)
        self.filter_combo.addItem("Reserved", RemnantStatus.RESERVED)
        self.filter_combo.addItem("Consumed", RemnantStatus.CONSUMED)
        self.filter_combo.addItem("Discarded", RemnantStatus.DISCARDED)
        self.filter_combo.currentIndexChanged.connect(self.refresh_table)

        h_box.addWidget(lbl_f)
        h_box.addWidget(self.filter_combo)
        layout.addLayout(h_box)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Remnant ID", "Section / Spec", "Grade", "Length (mm)",
            "Width (mm)", "Status", "Rack / Location", "Source Project"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Actions Row
        action_row = QHBoxLayout()
        btn_mark_reserved = QPushButton("Mark as Reserved")
        btn_mark_reserved.setProperty("class", "secondaryBtn")
        btn_mark_reserved.clicked.connect(lambda: self._set_status(RemnantStatus.RESERVED))

        btn_mark_reusable = QPushButton("Mark as Reusable")
        btn_mark_reusable.setProperty("class", "secondaryBtn")
        btn_mark_reusable.clicked.connect(lambda: self._set_status(RemnantStatus.REUSABLE))

        btn_mark_consumed = QPushButton("Mark as Consumed")
        btn_mark_consumed.setProperty("class", "secondaryBtn")
        btn_mark_consumed.clicked.connect(lambda: self._set_status(RemnantStatus.CONSUMED))

        btn_delete = QPushButton("Delete Remnant")
        btn_delete.setProperty("class", "secondaryBtn")
        btn_delete.clicked.connect(self._delete_remnant)

        action_row.addWidget(btn_mark_reserved)
        action_row.addWidget(btn_mark_reusable)
        action_row.addWidget(btn_mark_consumed)
        action_row.addWidget(btn_delete)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.refresh_table()

    def refresh_table(self):
        status_filter = self.filter_combo.currentData()
        remnants = self.remnant_repo.list_all(status_filter)
        self.table.setRowCount(len(remnants))

        for row, r in enumerate(remnants):
            self.table.setItem(row, 0, QTableWidgetItem(r.id))
            self.table.setItem(row, 1, QTableWidgetItem(r.designation))
            self.table.setItem(row, 2, QTableWidgetItem(r.grade))
            self.table.setItem(row, 3, QTableWidgetItem(f"{r.length_mm:.0f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{r.width_mm:.0f}" if r.width_mm else "-"))
            
            c_status = QTableWidgetItem(r.status.value if hasattr(r.status, 'value') else str(r.status))
            if str(r.status) == "REUSABLE" or getattr(r.status, 'value', '') == "REUSABLE":
                c_status.setForeground(Qt.GlobalColor.green)
            self.table.setItem(row, 5, c_status)
            
            self.table.setItem(row, 6, QTableWidgetItem(r.location))
            self.table.setItem(row, 7, QTableWidgetItem(r.source_project))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, r.id)

    def _get_selected_id(self) -> str:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _set_status(self, new_status: RemnantStatus):
        rid = self._get_selected_id()
        if rid:
            self.remnant_repo.update_status(rid, new_status)
            self.refresh_table()

    def _delete_remnant(self):
        rid = self._get_selected_id()
        if rid:
            self.remnant_repo.delete(rid)
            self.refresh_table()
