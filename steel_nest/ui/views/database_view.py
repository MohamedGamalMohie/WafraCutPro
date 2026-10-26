"""
Settings and Materials Catalog Database View
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QDialog, QFormLayout, QDoubleSpinBox, QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import Qt

from steel_nest.database.db_manager import DatabaseManager
from steel_nest.config import STANDARD_SECTIONS, STANDARD_STEEL_GRADES

class AddCustomMaterialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Steel Profile")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.desig_edit = QLineEdit()
        self.family_combo = QComboBox()
        self.family_combo.addItems(["IPE", "HEA", "HEB", "HEM", "UPN", "L (Angle)", "SHS", "RHS", "CHS", "FLAT", "ROUND", "CUSTOM"])
        
        self.grade_combo = QComboBox()
        for g in STANDARD_STEEL_GRADES:
            self.grade_combo.addItem(g)

        self.wt_spin = QDoubleSpinBox()
        self.wt_spin.setRange(0.1, 1000.0)
        self.wt_spin.setValue(25.0)
        self.wt_spin.setSuffix(" kg/m")

        self.notes_edit = QLineEdit("User-defined profile")

        form.addRow("Designation* (e.g. W12x50):", self.desig_edit)
        form.addRow("Family:", self.family_combo)
        form.addRow("Standard Grade:", self.grade_combo)
        form.addRow("Weight per meter:", self.wt_spin)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_save = QPushButton("Save Profile")
        btn_save.setProperty("class", "primaryBtn")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _save(self):
        if not self.desig_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Designation cannot be empty.")
            return
        self.accept()

    def get_data(self):
        return (
            self.desig_edit.text().strip(),
            self.family_combo.currentText().strip(),
            self.grade_combo.currentText().strip(),
            self.wt_spin.value(),
            "LINEAR",
            self.notes_edit.text().strip()
        )

class DatabaseView(QWidget):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        h_title = QLabel("Steel Materials Catalog & Database")
        h_title.setObjectName("viewTitle")
        h_sub = QLabel("Standard engineering steel profiles catalog (European & American standards) and custom section definitions.")
        h_sub.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_box.addLayout(title_box)
        h_box.addStretch()

        btn_add = QPushButton("+ Add Custom Profile")
        btn_add.setProperty("class", "primaryBtn")
        btn_add.clicked.connect(self._add_custom)
        h_box.addWidget(btn_add)
        layout.addLayout(h_box)

        # Filter & Search row
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search profiles (e.g. IPE, HEA, L, 300)...")
        self.search_edit.textChanged.connect(self.refresh_table)

        self.family_filter = QComboBox()
        self.family_filter.addItem("All Families", "")
        for fam in ["IPE", "HEA", "HEB", "UPN", "L", "SHS", "RHS", "CHS"]:
            self.family_filter.addItem(fam, fam)
        self.family_filter.currentIndexChanged.connect(self.refresh_table)

        search_row.addWidget(QLabel("Search:"))
        search_row.addWidget(self.search_edit, 3)
        search_row.addWidget(QLabel("Family:"))
        search_row.addWidget(self.family_filter, 1)
        layout.addLayout(search_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Designation", "Family", "Grade", "Weight (kg/m)", "Type / Notes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.refresh_table()

    def refresh_table(self):
        search_txt = self.search_edit.text().strip().lower()
        family_sel = self.family_filter.currentData()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM materials WHERE 1=1"
            params = []
            if family_sel:
                query += " AND family LIKE ?"
                params.append(f"%{family_sel}%")
            if search_txt:
                query += " AND (LOWER(designation) LIKE ? OR LOWER(grade) LIKE ?)"
                params.append(f"%{search_txt}%")
                params.append(f"%{search_txt}%")
            query += " ORDER BY designation ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

        self.table.setRowCount(len(rows))
        for r_idx, r in enumerate(rows):
            self.table.setItem(r_idx, 0, QTableWidgetItem(r["designation"]))
            self.table.setItem(r_idx, 1, QTableWidgetItem(r["family"]))
            self.table.setItem(r_idx, 2, QTableWidgetItem(r["grade"]))
            self.table.setItem(r_idx, 3, QTableWidgetItem(f"{r['weight_kg_per_m']:.2f}"))
            self.table.setItem(r_idx, 4, QTableWidgetItem(r["notes"] or ""))

    def _add_custom(self):
        dlg = AddCustomMaterialDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            with self.db.get_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO materials (designation, family, grade, weight_kg_per_m, material_type, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """, data)
                conn.commit()
            self.refresh_table()
            QMessageBox.information(self, "Material Saved", f"Profile '{data[0]}' added to database.")
