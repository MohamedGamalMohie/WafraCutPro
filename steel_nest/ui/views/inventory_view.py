"""
Stock Inventory Management View
"""
import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt

from steel_nest.models.stock import StockItem
from steel_nest.database.repositories import StockRepository
from steel_nest.reporting.excel_importer import ExcelDataImporter
from steel_nest.reporting.template_generator import TemplateGenerator
from steel_nest.config import STANDARD_SECTIONS, STANDARD_STEEL_GRADES, MaterialType

class AddStockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock Item")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItems(["LINEAR (Profile/Beam/Pipe)", "PLATE (Sheet/Plate)"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        self.id_edit = QLineEdit(f"STK-{uuid.uuid4().hex[:6].upper()}")
        
        self.desig_combo = QComboBox()
        self.desig_combo.setEditable(True)
        for fam, profs in STANDARD_SECTIONS.items():
            for d, _ in profs:
                self.desig_combo.addItem(d)

        self.grade_combo = QComboBox()
        for g in STANDARD_STEEL_GRADES:
            self.grade_combo.addItem(g)

        self.len_spin = QDoubleSpinBox()
        self.len_spin.setRange(100.0, 30000.0)
        self.len_spin.setValue(12000.0)
        self.len_spin.setSuffix(" mm")

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.0, 5000.0)
        self.width_spin.setValue(0.0)
        self.width_spin.setSuffix(" mm")
        self.width_spin.setEnabled(False)

        self.thk_spin = QDoubleSpinBox()
        self.thk_spin.setRange(0.0, 150.0)
        self.thk_spin.setValue(0.0)
        self.thk_spin.setSuffix(" mm")
        self.thk_spin.setEnabled(False)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 10000)
        self.qty_spin.setValue(10)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0.0, 100000.0)
        self.cost_spin.setValue(350.0)
        self.cost_spin.setPrefix("$ ")

        self.loc_edit = QLineEdit("Warehouse A")
        self.notes_edit = QLineEdit("Standard Mill Stock")

        form.addRow("Material Type:", self.type_combo)
        form.addRow("Stock ID*:", self.id_edit)
        form.addRow("Section Designation*:", self.desig_combo)
        form.addRow("Steel Grade*:", self.grade_combo)
        form.addRow("Stock Length*:", self.len_spin)
        form.addRow("Stock Width (Plates):", self.width_spin)
        form.addRow("Thickness (Plates):", self.thk_spin)
        form.addRow("Available Quantity*:", self.qty_spin)
        form.addRow("Unit Purchasing Cost:", self.cost_spin)
        form.addRow("Storage Location:", self.loc_edit)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_save = QPushButton("Add to Inventory")
        btn_save.setProperty("class", "primaryBtn")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setProperty("class", "secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _on_type_changed(self, idx):
        is_plate = (idx == 1)
        self.width_spin.setEnabled(is_plate)
        self.thk_spin.setEnabled(is_plate)
        if is_plate:
            self.len_spin.setValue(6000.0)
            self.width_spin.setValue(2000.0)
            self.thk_spin.setValue(12.0)
            self.desig_combo.setEditText("PL 12mm")
        else:
            self.len_spin.setValue(12000.0)
            self.width_spin.setValue(0.0)
            self.thk_spin.setValue(0.0)
            self.desig_combo.setEditText("IPE 300")

    def get_stock(self) -> StockItem:
        is_plate = (self.type_combo.currentIndex() == 1)
        return StockItem(
            id=self.id_edit.text().strip(),
            designation=self.desig_combo.currentText().strip(),
            grade=self.grade_combo.currentText().strip(),
            length_mm=self.len_spin.value(),
            width_mm=self.width_spin.value() if is_plate else 0.0,
            thickness_mm=self.thk_spin.value() if is_plate else 0.0,
            available_qty=self.qty_spin.value(),
            used_qty=0,
            cost_per_unit=self.cost_spin.value(),
            is_remnant=False,
            location=self.loc_edit.text().strip(),
            material_type=MaterialType.PLATE if is_plate else MaterialType.LINEAR,
            notes=self.notes_edit.text().strip()
        )

class InventoryView(QWidget):
    def __init__(self, stock_repo: StockRepository, parent=None):
        super().__init__(parent)
        self.stock_repo = stock_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        h_title = QLabel("Stock Inventory & Purchasing")
        h_title.setObjectName("viewTitle")
        h_sub = QLabel("Manage standard length bars, plates, purchase costs, and track available quantities.")
        h_sub.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_box.addLayout(title_box)
        h_box.addStretch()

        btn_seed = QPushButton("Seed Demo Stock")
        btn_seed.setProperty("class", "secondaryBtn")
        btn_seed.clicked.connect(self._seed_demo_stock)

        btn_import = QPushButton("Import Inventory Excel")
        btn_import.setProperty("class", "secondaryBtn")
        btn_import.clicked.connect(self._import_stock)

        h_box.addWidget(btn_seed)
        h_box.addWidget(btn_import)
        layout.addLayout(h_box)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Stock ID", "Type", "Designation", "Grade", "Length (mm)",
            "Width (mm)", "Available Qty", "Unit Cost ($)", "Location"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Action Buttons
        action_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Stock Item")
        btn_add.setProperty("class", "primaryBtn")
        btn_add.clicked.connect(self._add_stock)

        btn_del = QPushButton("Delete Selected")
        btn_del.setProperty("class", "secondaryBtn")
        btn_del.clicked.connect(self._delete_stock)

        action_row.addWidget(btn_add)
        action_row.addWidget(btn_del)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.refresh_table()

    def refresh_table(self):
        items = self.stock_repo.list_all()
        self.table.setRowCount(len(items))
        for row, s in enumerate(items):
            rem_qty = s.available_qty - s.used_qty
            self.table.setItem(row, 0, QTableWidgetItem(s.id))
            self.table.setItem(row, 1, QTableWidgetItem(s.material_type.value if hasattr(s.material_type, 'value') else str(s.material_type)))
            self.table.setItem(row, 2, QTableWidgetItem(s.designation))
            self.table.setItem(row, 3, QTableWidgetItem(s.grade))
            self.table.setItem(row, 4, QTableWidgetItem(f"{s.length_mm:.0f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{s.width_mm:.0f}" if s.width_mm else "-"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{rem_qty} / {s.available_qty}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"${s.cost_per_unit:.2f}" if s.cost_per_unit else "$0.00"))
            self.table.setItem(row, 8, QTableWidgetItem(s.location))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s.id)

    def _add_stock(self):
        dlg = AddStockDialog(parent=self)
        if dlg.exec():
            stock = dlg.get_stock()
            self.stock_repo.add(stock)
            self.refresh_table()

    def _delete_stock(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                sid = item.data(Qt.ItemDataRole.UserRole)
                self.stock_repo.delete(sid)
                self.refresh_table()

    def _seed_demo_stock(self):
        demo_items = [
            # IPE 300 in 12m and 6m
            StockItem(id="STK-IPE300-12M", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=20, cost_per_unit=550.0, location="Bay 1"),
            StockItem(id="STK-IPE300-6M", designation="IPE 300", grade="S355JR", length_mm=6000.0, available_qty=10, cost_per_unit=285.0, location="Bay 1"),
            # HEA 200 in 12m
            StockItem(id="STK-HEA200-12M", designation="HEA 200", grade="S355JR", length_mm=12000.0, available_qty=15, cost_per_unit=490.0, location="Bay 2"),
            # UPN 160 in 12m
            StockItem(id="STK-UPN160-12M", designation="UPN 160", grade="S275JR", length_mm=12000.0, available_qty=12, cost_per_unit=260.0, location="Bay 3"),
            # Angles L 60x60x6 in 6m
            StockItem(id="STK-L60-6M", designation="L 60x60x6", grade="S275JR", length_mm=6000.0, available_qty=25, cost_per_unit=65.0, location="Bay 4"),
            # Plates
            StockItem(id="STK-PL12-2x6", designation="PL 12mm", grade="S275JR", length_mm=6000.0, width_mm=2000.0, thickness_mm=12.0, available_qty=6, cost_per_unit=1150.0, material_type=MaterialType.PLATE, location="Plate Yard"),
            StockItem(id="STK-PL20-2x6", designation="PL 20mm", grade="S355JR", length_mm=6000.0, width_mm=2000.0, thickness_mm=20.0, available_qty=4, cost_per_unit=1800.0, material_type=MaterialType.PLATE, location="Plate Yard")
        ]
        for it in demo_items:
            self.stock_repo.add(it)
        self.refresh_table()
        QMessageBox.information(self, "Demo Stock Added", "Standard inventory profiles and plates seeded successfully!")

    def _import_stock(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Stock Inventory", "", "Excel / CSV Files (*.xlsx *.csv)")
        if not path:
            return
        items, errs = ExcelDataImporter.import_stock_inventory(path)
        for it in items:
            self.stock_repo.add(it)
        self.refresh_table()
        msg = f"Imported {len(items)} stock items."
        if errs:
            msg += "\n\nWarnings:\n" + "\n".join(errs[:5])
        QMessageBox.information(self, "Import Results", msg)
