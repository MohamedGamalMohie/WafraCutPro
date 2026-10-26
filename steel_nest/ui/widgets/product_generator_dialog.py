"""
Complex Products Definition and Parametric Generator for SteelNest Pro
Allows wood, cabinet, and fabrication workshops to generate complete cut lists
for standard products (Cabinets, Cupboards, Bookshelves, Desks, Drawers)
based on external product dimensions and board thickness.
"""
from typing import List, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFormLayout, QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QMessageBox
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

class ProductGeneratorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ Complex Product Generator — مولد المنتجات المركبة")
        self.resize(750, 560)
        self.generated_parts: List[Tuple[str, float, float, int, str]] = [] # (mark, length, width, qty, label)
        self._init_ui()
        self._calculate_parts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Header Banner
        header = QLabel("اختر نوع المنتج وأدخل الأبعاد الخارجية لحساب جدول القطعيات تلقائياً:")
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(header)

        # Top Form Row
        form_box = QGroupBox("مواصفات المنتج (Product Specifications)")
        form_layout = QFormLayout(form_box)

        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "دولاب / كابينت مطبخ (Kitchen Cabinet / Cupboard)",
            "مكتبة أرفف (Bookshelf / Bookcase)",
            "مكتب عمل / طاولة (Desk / Office Table)",
            "صندوق درج (Drawer Box)"
        ])
        self.combo_type.currentIndexChanged.connect(self._calculate_parts)
        form_layout.addRow("نوع المنتج (Type):", self.combo_type)

        dims_row = QHBoxLayout()
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(100.0, 4000.0)
        self.spin_height.setValue(800.0)
        self.spin_height.setSuffix(" mm")
        self.spin_height.valueChanged.connect(self._calculate_parts)

        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(100.0, 4000.0)
        self.spin_width.setValue(600.0)
        self.spin_width.setSuffix(" mm")
        self.spin_width.valueChanged.connect(self._calculate_parts)

        self.spin_depth = QDoubleSpinBox()
        self.spin_depth.setRange(50.0, 2000.0)
        self.spin_depth.setValue(400.0)
        self.spin_depth.setSuffix(" mm")
        self.spin_depth.valueChanged.connect(self._calculate_parts)

        dims_row.addWidget(QLabel("الارتفاع (H):"))
        dims_row.addWidget(self.spin_height)
        dims_row.addWidget(QLabel("العرض (W):"))
        dims_row.addWidget(self.spin_width)
        dims_row.addWidget(QLabel("العمق (D):"))
        dims_row.addWidget(self.spin_depth)
        form_layout.addRow("الأبعاد الخارجية:", dims_row)

        sub_row = QHBoxLayout()
        self.spin_thick = QDoubleSpinBox()
        self.spin_thick.setRange(1.0, 100.0)
        self.spin_thick.setValue(18.0)
        self.spin_thick.setSuffix(" mm")
        self.spin_thick.valueChanged.connect(self._calculate_parts)

        self.spin_shelves = QSpinBox()
        self.spin_shelves.setRange(0, 20)
        self.spin_shelves.setValue(2)
        self.spin_shelves.valueChanged.connect(self._calculate_parts)

        self.spin_product_qty = QSpinBox()
        self.spin_product_qty.setRange(1, 1000)
        self.spin_product_qty.setValue(1)
        self.spin_product_qty.valueChanged.connect(self._calculate_parts)

        sub_row.addWidget(QLabel("سمك اللوح (T):"))
        sub_row.addWidget(self.spin_thick)
        sub_row.addWidget(QLabel("عدد الأرفف:"))
        sub_row.addWidget(self.spin_shelves)
        sub_row.addWidget(QLabel("عدد الوحدات:"))
        sub_row.addWidget(self.spin_product_qty)
        form_layout.addRow("التفاصيل والكمية:", sub_row)

        main_layout.addWidget(form_box)

        # Parts Preview Table
        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(5)
        self.table_preview.setHorizontalHeaderLabels([
            "اسم القطعة (Component)", "الطول (Length)", "العرض (Width)", "الكمية (Qty)", "الملاحظات"
        ])
        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_preview.setAlternatingRowColors(True)
        main_layout.addWidget(self.table_preview, 1)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_apply = QPushButton("➕ إدراج في جدول القطعيات (Insert into Cut List)")
        btn_apply.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 7px 18px;")
        btn_apply.clicked.connect(self._apply_and_close)

        btn_cancel = QPushButton("إلغاء (Cancel)")
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_apply)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        main_layout.addLayout(btn_row)

    def _calculate_parts(self):
        prod_idx = self.combo_type.currentIndex()
        h = self.spin_height.value()
        w = self.spin_width.value()
        d = self.spin_depth.value()
        t = self.spin_thick.value()
        n_shelves = self.spin_shelves.value()
        units = self.spin_product_qty.value()

        parts = []

        if prod_idx == 0: # Cabinet / Cupboard
            # Sides (2)
            parts.append(("Side-L", h, d, 1 * units, "Left side panel"))
            parts.append(("Side-R", h, d, 1 * units, "Right side panel"))
            # Top & Bottom (2)
            inner_w = max(10.0, w - 2 * t)
            parts.append(("Top", inner_w, d, 1 * units, "Top panel"))
            parts.append(("Bottom", inner_w, d, 1 * units, "Bottom panel"))
            # Shelves
            if n_shelves > 0:
                parts.append(("Shelf", inner_w, max(10.0, d - 15.0), n_shelves * units, f"{n_shelves} adjustable shelves"))
            # Back Panel
            parts.append(("Back", max(10.0, h - 2 * t), inner_w, 1 * units, "Back panel"))
            # Doors
            door_w = max(10.0, (w - 6.0) / 2.0)
            parts.append(("Door", max(10.0, h - 6.0), door_w, 2 * units, "Front pair doors"))

        elif prod_idx == 1: # Bookshelf
            parts.append(("Side-L", h, d, 1 * units, "Left side"))
            parts.append(("Side-R", h, d, 1 * units, "Right side"))
            inner_w = max(10.0, w - 2 * t)
            parts.append(("Top", inner_w, d, 1 * units, "Top cap"))
            parts.append(("Bottom", inner_w, d, 1 * units, "Bottom base"))
            if n_shelves > 0:
                parts.append(("Shelf", inner_w, d, n_shelves * units, f"{n_shelves} shelves"))
            parts.append(("Back", h, w, 1 * units, "Back board"))

        elif prod_idx == 2: # Desk / Table
            parts.append(("Desk-Top", w, d, 1 * units, "Worktop"))
            parts.append(("Leg-L", max(10.0, h - t), d, 1 * units, "Left side panel"))
            parts.append(("Leg-R", max(10.0, h - t), d, 1 * units, "Right side panel"))
            parts.append(("Modesty", max(10.0, w - 2 * t), max(10.0, (h - t) * 0.4), 1 * units, "Back support panel"))

        elif prod_idx == 3: # Drawer Box
            parts.append(("Drw-Side", d, h, 2 * units, "Drawer sides"))
            inner_w = max(10.0, w - 2 * t)
            parts.append(("Drw-Front", inner_w, h, 1 * units, "Drawer inner front"))
            parts.append(("Drw-Back", inner_w, h, 1 * units, "Drawer inner back"))
            parts.append(("Drw-Bottom", inner_w, max(10.0, d - 2 * t), 1 * units, "Drawer bottom"))

        self.generated_parts = parts
        self.table_preview.setRowCount(len(parts))
        for r, (mark, length, width, qty, notes) in enumerate(parts):
            self.table_preview.setItem(r, 0, QTableWidgetItem(mark))
            self.table_preview.setItem(r, 1, QTableWidgetItem(f"{length:.1f}"))
            self.table_preview.setItem(r, 2, QTableWidgetItem(f"{width:.1f}"))
            self.table_preview.setItem(r, 3, QTableWidgetItem(str(qty)))
            self.table_preview.setItem(r, 4, QTableWidgetItem(notes))

    def _apply_and_close(self):
        if not self.generated_parts:
            QMessageBox.warning(self, "تنبيه", "لا توجد قطعيات تم إنشاؤها.")
            return
        self.accept()

    def get_parts(self) -> List[Tuple[str, float, float, int, str]]:
        return self.generated_parts
