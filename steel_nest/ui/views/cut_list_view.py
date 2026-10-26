"""
Cut List View for 1D Linear Profiles and 2D Steel Plates
"""
import uuid
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt

from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.database.repositories import CutListRepository, ProjectRepository, StockRepository
from steel_nest.reporting.excel_importer import ExcelDataImporter
from steel_nest.reporting.template_generator import TemplateGenerator
from steel_nest.config import STANDARD_SECTIONS, STANDARD_STEEL_GRADES

class AddLinearPartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Linear Cut Part")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mark_edit = QLineEdit(f"B-{uuid.uuid4().hex[:3].upper()}")
        
        self.desig_combo = QComboBox()
        self.desig_combo.setEditable(True)
        # Populate standard profiles
        for fam, profs in STANDARD_SECTIONS.items():
            for d, _ in profs:
                self.desig_combo.addItem(d)

        self.grade_combo = QComboBox()
        for g in STANDARD_STEEL_GRADES:
            self.grade_combo.addItem(g)

        self.len_spin = QDoubleSpinBox()
        self.len_spin.setRange(10.0, 30000.0)
        self.len_spin.setValue(4500.0)
        self.len_spin.setSuffix(" mm")

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)

        self.notes_edit = QLineEdit()

        form.addRow("Part Mark*:", self.mark_edit)
        form.addRow("Section Designation*:", self.desig_combo)
        form.addRow("Steel Grade*:", self.grade_combo)
        form.addRow("Cut Length*:", self.len_spin)
        form.addRow("Quantity*:", self.qty_spin)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_save = QPushButton("Add Part")
        btn_save.setProperty("class", "primaryBtn")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_part(self) -> PartCutItem:
        return PartCutItem(
            id=str(uuid.uuid4()),
            mark=self.mark_edit.text().strip(),
            designation=self.desig_combo.currentText().strip(),
            grade=self.grade_combo.currentText().strip(),
            length_mm=self.len_spin.value(),
            quantity=self.qty_spin.value(),
            notes=self.notes_edit.text().strip()
        )

class AddPlatePartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add 2D Plate Part")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mark_edit = QLineEdit(f"PL-{uuid.uuid4().hex[:3].upper()}")
        self.thick_spin = QDoubleSpinBox()
        self.thick_spin.setRange(1.0, 150.0)
        self.thick_spin.setValue(12.0)
        self.thick_spin.setSuffix(" mm")

        self.grade_combo = QComboBox()
        for g in STANDARD_STEEL_GRADES:
            self.grade_combo.addItem(g)

        self.w_spin = QDoubleSpinBox()
        self.w_spin.setRange(10.0, 5000.0)
        self.w_spin.setValue(350.0)
        self.w_spin.setSuffix(" mm")

        self.l_spin = QDoubleSpinBox()
        self.l_spin.setRange(10.0, 15000.0)
        self.l_spin.setValue(600.0)
        self.l_spin.setSuffix(" mm")

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)

        self.rot_check = QCheckBox("Allow 90° Rotation")
        self.rot_check.setChecked(True)

        self.notes_edit = QLineEdit()

        form.addRow("Part Mark*:", self.mark_edit)
        form.addRow("Plate Thickness*:", self.thick_spin)
        form.addRow("Steel Grade*:", self.grade_combo)
        form.addRow("Part Width*:", self.w_spin)
        form.addRow("Part Length*:", self.l_spin)
        form.addRow("Quantity*:", self.qty_spin)
        form.addRow("Rotation:", self.rot_check)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_save = QPushButton("Add Plate Part")
        btn_save.setProperty("class", "primaryBtn")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_part(self) -> PlatePartItem:
        return PlatePartItem(
            id=str(uuid.uuid4()),
            mark=self.mark_edit.text().strip(),
            thickness_mm=self.thick_spin.value(),
            grade=self.grade_combo.currentText().strip(),
            width_mm=self.w_spin.value(),
            length_mm=self.l_spin.value(),
            quantity=self.qty_spin.value(),
            allow_rotation=self.rot_check.isChecked(),
            notes=self.notes_edit.text().strip()
        )

class CutListView(QWidget):
    def __init__(self, cut_repo: CutListRepository, project_repo: ProjectRepository, stock_repo: StockRepository, parent=None):
        super().__init__(parent)
        self.cut_repo = cut_repo
        self.project_repo = project_repo
        self.stock_repo = stock_repo
        self.active_project_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("Cut Lists & Part Requirements")
        self.title_lbl.setObjectName("viewTitle")
        self.sub_lbl = QLabel("Manage required structural steel cut lengths and plate dimensions.")
        self.sub_lbl.setObjectName("viewSubtitle")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        h_box.addLayout(title_box)
        h_box.addStretch()

        # Action Buttons
        btn_import = QPushButton("Import Excel / CSV")
        btn_import.setProperty("class", "secondaryBtn")
        btn_import.clicked.connect(self._import_file)
        
        btn_template = QPushButton("Get Blank Template")
        btn_template.setProperty("class", "secondaryBtn")
        btn_template.clicked.connect(self._download_template)

        h_box.addWidget(btn_import)
        h_box.addWidget(btn_template)
        layout.addLayout(h_box)

        # Tab Widget for Linear vs Plate
        self.tabs = QTabWidget()
        
        # TAB 1: Linear Profiles
        self.linear_widget = QWidget()
        l_layout = QVBoxLayout(self.linear_widget)
        l_layout.setContentsMargins(10, 10, 10, 10)

        self.linear_table = QTableWidget()
        self.linear_table.setColumnCount(7)
        self.linear_table.setHorizontalHeaderLabels(["Mark", "Section", "Grade", "Length (mm)", "Qty", "Weight (kg)", "Notes"])
        self.linear_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.linear_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        l_layout.addWidget(self.linear_table)

        l_actions = QHBoxLayout()
        btn_add_linear = QPushButton("+ Add Linear Part")
        btn_add_linear.setProperty("class", "primaryBtn")
        btn_add_linear.clicked.connect(self._add_linear_part)
        
        btn_del_linear = QPushButton("Delete Selected")
        btn_del_linear.setProperty("class", "secondaryBtn")
        btn_del_linear.clicked.connect(self._delete_linear_part)

        btn_clear_linear = QPushButton("Clear All Linear")
        btn_clear_linear.setProperty("class", "secondaryBtn")
        btn_clear_linear.clicked.connect(self._clear_linear)

        l_actions.addWidget(btn_add_linear)
        l_actions.addWidget(btn_del_linear)
        l_actions.addWidget(btn_clear_linear)
        l_actions.addStretch()
        l_layout.addLayout(l_actions)

        self.tabs.addTab(self.linear_widget, "1D Structural Sections (Beams, Angles, Hollow)")

        # TAB 2: Plates
        self.plate_widget = QWidget()
        p_layout = QVBoxLayout(self.plate_widget)
        p_layout.setContentsMargins(10, 10, 10, 10)

        self.plate_table = QTableWidget()
        self.plate_table.setColumnCount(8)
        self.plate_table.setHorizontalHeaderLabels(["Mark", "Thk (mm)", "Grade", "Width (mm)", "Length (mm)", "Qty", "Rotation", "Notes"])
        self.plate_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.plate_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        p_layout.addWidget(self.plate_table)

        p_actions = QHBoxLayout()
        btn_add_plate = QPushButton("+ Add Plate Part")
        btn_add_plate.setProperty("class", "primaryBtn")
        btn_add_plate.clicked.connect(self._add_plate_part)

        btn_del_plate = QPushButton("Delete Selected")
        btn_del_plate.setProperty("class", "secondaryBtn")
        btn_del_plate.clicked.connect(self._delete_plate_part)

        btn_clear_plate = QPushButton("Clear All Plate")
        btn_clear_plate.setProperty("class", "secondaryBtn")
        btn_clear_plate.clicked.connect(self._clear_plate)

        p_actions.addWidget(btn_add_plate)
        p_actions.addWidget(btn_del_plate)
        p_actions.addWidget(btn_clear_plate)
        p_actions.addStretch()
        p_layout.addLayout(p_actions)

        self.tabs.addTab(self.plate_widget, "2D Steel Plates & Sheets")
        layout.addWidget(self.tabs)

    def set_active_project(self, project_id: str):
        self.active_project_id = project_id
        proj = self.project_repo.get(project_id)
        if proj:
            self.sub_lbl.setText(f"Project: {proj.name} ({proj.code})")
        self.refresh_tables()

    def refresh_tables(self):
        if not self.active_project_id:
            self.linear_table.setRowCount(0)
            self.plate_table.setRowCount(0)
            return

        # Linear
        parts_1d = self.cut_repo.list_linear_by_project(self.active_project_id)
        self.linear_table.setRowCount(len(parts_1d))
        for row, p in enumerate(parts_1d):
            self.linear_table.setItem(row, 0, QTableWidgetItem(p.mark))
            self.linear_table.setItem(row, 1, QTableWidgetItem(p.designation))
            self.linear_table.setItem(row, 2, QTableWidgetItem(p.grade))
            self.linear_table.setItem(row, 3, QTableWidgetItem(f"{p.length_mm:.1f}"))
            self.linear_table.setItem(row, 4, QTableWidgetItem(str(p.quantity)))
            self.linear_table.setItem(row, 5, QTableWidgetItem(f"{p.weight_kg:.1f}"))
            self.linear_table.setItem(row, 6, QTableWidgetItem(p.notes))
            self.linear_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

        # Plate
        parts_2d = self.cut_repo.list_plate_by_project(self.active_project_id)
        self.plate_table.setRowCount(len(parts_2d))
        for row, p in enumerate(parts_2d):
            self.plate_table.setItem(row, 0, QTableWidgetItem(p.mark))
            self.plate_table.setItem(row, 1, QTableWidgetItem(f"{p.thickness_mm:.1f}"))
            self.plate_table.setItem(row, 2, QTableWidgetItem(p.grade))
            self.plate_table.setItem(row, 3, QTableWidgetItem(f"{p.width_mm:.1f}"))
            self.plate_table.setItem(row, 4, QTableWidgetItem(f"{p.length_mm:.1f}"))
            self.plate_table.setItem(row, 5, QTableWidgetItem(str(p.quantity)))
            self.plate_table.setItem(row, 6, QTableWidgetItem("YES" if p.allow_rotation else "NO"))
            self.plate_table.setItem(row, 7, QTableWidgetItem(p.notes))
            self.plate_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _add_linear_part(self):
        if not self._check_project():
            return
        dlg = AddLinearPartDialog(parent=self)
        if dlg.exec():
            part = dlg.get_part()
            self.cut_repo.add_linear(part, self.active_project_id)
            self.refresh_tables()

    def _delete_linear_part(self):
        row = self.linear_table.currentRow()
        if row >= 0:
            item = self.linear_table.item(row, 0)
            if item:
                pid = item.data(Qt.ItemDataRole.UserRole)
                self.cut_repo.delete_linear(pid)
                self.refresh_tables()

    def _clear_linear(self):
        if self._check_project():
            if QMessageBox.question(self, "Clear Linear Parts", "Are you sure you want to clear all linear cut requirements?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.cut_repo.clear_linear(self.active_project_id)
                self.refresh_tables()

    def _add_plate_part(self):
        if not self._check_project():
            return
        dlg = AddPlatePartDialog(parent=self)
        if dlg.exec():
            part = dlg.get_part()
            self.cut_repo.add_plate(part, self.active_project_id)
            self.refresh_tables()

    def _delete_plate_part(self):
        row = self.plate_table.currentRow()
        if row >= 0:
            item = self.plate_table.item(row, 0)
            if item:
                pid = item.data(Qt.ItemDataRole.UserRole)
                self.cut_repo.delete_plate(pid)
                self.refresh_tables()

    def _clear_plate(self):
        if self._check_project():
            if QMessageBox.question(self, "Clear Plate Parts", "Are you sure you want to clear all plate cut requirements?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.cut_repo.clear_plate(self.active_project_id)
                self.refresh_tables()

    def _check_project(self) -> bool:
        if not self.active_project_id:
            QMessageBox.information(self, "Select Project", "Please create or select an active project first in Projects view.")
            return False
        return True

    def _import_file(self):
        if not self._check_project():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import Cut List", "", "Excel / CSV Files (*.xlsx *.csv)")
        if not path:
            return

        is_plate_tab = (self.tabs.currentIndex() == 1)
        if is_plate_tab:
            parts, errs = ExcelDataImporter.import_plate_cut_list(path)
            for p in parts:
                self.cut_repo.add_plate(p, self.active_project_id)
        else:
            parts, errs = ExcelDataImporter.import_linear_cut_list(path)
            for p in parts:
                self.cut_repo.add_linear(p, self.active_project_id)

        self.refresh_tables()
        msg = f"Successfully imported {len(parts)} parts."
        if errs:
            msg += f"\n\nWarnings/Errors:\n" + "\n".join(errs[:5])
        QMessageBox.information(self, "Import Results", msg)

    def _download_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Input Template", "SteelNest_CutList_Template.xlsx", "Excel Files (*.xlsx)")
        if path:
            if self.tabs.currentIndex() == 1:
                TemplateGenerator.generate_plate_cut_list_template(path)
            else:
                TemplateGenerator.generate_linear_cut_list_template(path)
            QMessageBox.information(self, "Template Saved", f"Blank template saved to:\n{path}")
