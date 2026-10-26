"""
Easy Unified Nesting View (1D Profiles + 2D Plates combined)
Combines Linear parts (Width=0) and Plate parts (Width>0) into a single,
ultra-intuitive workspace with zero complication.
"""
import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QRadioButton, QButtonGroup, QDoubleSpinBox, QSpinBox,
    QComboBox, QMessageBox, QFileDialog, QSplitter, QFrame,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.models.project import Project, ProjectSettings
from steel_nest.config import (
    LinearOptimizationMode, NestingObjective, MaterialType
)
from steel_nest.database.repositories import CutListRepository, StockRepository, ProjectRepository
from steel_nest.reporting.excel_importer import ExcelDataImporter
from steel_nest.reporting.template_generator import TemplateGenerator
from steel_nest.ui.workers.optimization_worker import OptimizationWorker
from steel_nest.models.nesting_plan import OptimizationResult

class EasyNestingView(QWidget):
    optimization_finished = pyqtSignal(object)  # OptimizationResult

    def __init__(
        self,
        cut_repo: CutListRepository,
        stock_repo: StockRepository,
        project_repo: ProjectRepository,
        parent=None
    ):
        super().__init__(parent)
        self.cut_repo = cut_repo
        self.stock_repo = stock_repo
        self.project_repo = project_repo
        self.active_project_id = None
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 1. Top Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:1 #1E293B);
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 6, 8, 6)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        h_title = QLabel("⚡ مساحة التقطيع الشاملة (1D الكمرات + 2D ألواح الصاج معاً)")
        h_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        h_title.setStyleSheet("color: #FFFFFF;")
        h_sub = QLabel("ملاحظة: المقاطع الطولية والكمرات العرض = 0 | ألواح الصاج اكتب العرض المطلوب > 0")
        h_sub.setStyleSheet("color: #93C5FD; font-size: 11px; font-weight: bold;")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch()

        btn_demo = QPushButton("✨ تحميل بيانات تجريبية (Load Demo)")
        btn_demo.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 6px 14px; border-radius: 5px;")
        btn_demo.clicked.connect(self._load_demo_data)

        btn_import_excel = QPushButton("📥 استيراد من إكسيل (Import)")
        btn_import_excel.setProperty("class", "secondaryBtn")
        btn_import_excel.clicked.connect(self._import_excel)

        btn_template = QPushButton("📄 تحميل نموذج إكسيل (Template)")
        btn_template.setProperty("class", "secondaryBtn")
        btn_template.clicked.connect(self._download_template)

        h_layout.addWidget(btn_demo)
        h_layout.addWidget(btn_import_excel)
        h_layout.addWidget(btn_template)
        layout.addWidget(header_frame)

        # 2. Main Vertical Splitter:
        #    Top Table: Cut Pieces (القطع المطلوبة)
        #    Bottom Table: Stock Available (الاستوك المتاح)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- SECTION A: CUT LIST TABLE ---
        parts_box = QGroupBox("1. القطع المطلوب تفصيلها (الكمرات: العرض=0 | الصاج: اكتب العرض)")
        parts_box.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p_layout = QVBoxLayout(parts_box)
        p_layout.setContentsMargins(8, 8, 8, 8)
        p_layout.setSpacing(6)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(7)
        self.parts_table.setHorizontalHeaderLabels([
            "كود القطعة (Mark)", "القطاع / الخامة (Section)", "الرتبة (Grade)",
            "الطول (Length mm)", "العرض (Width mm)", "العدد (Qty)", "دوران الصاج 90° (Rotate)"
        ])
        self.parts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.parts_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.parts_table.cellChanged.connect(self._on_part_cell_changed)
        p_layout.addWidget(self.parts_table)

        # Parts action buttons
        p_btns = QHBoxLayout()
        btn_add_beam = QPushButton("+ إضافة كمرة / قطاع طولي (عرض=0)")
        btn_add_beam.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        btn_add_beam.clicked.connect(self._add_beam_row)

        btn_add_plate = QPushButton("+ إضافة لوح / قطعة صاج (عرض>0)")
        btn_add_plate.setStyleSheet("background-color: #7C3AED; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        btn_add_plate.clicked.connect(self._add_plate_row)

        btn_del_part = QPushButton("❌ حذف المحدد (Delete)")
        btn_del_part.setProperty("class", "secondaryBtn")
        btn_del_part.clicked.connect(self._delete_part_row)

        btn_clear_parts = QPushButton("مسح جدول القطع (Clear)")
        btn_clear_parts.setProperty("class", "secondaryBtn")
        btn_clear_parts.clicked.connect(self._clear_parts)

        p_btns.addWidget(btn_add_beam)
        p_btns.addWidget(btn_add_plate)
        p_btns.addWidget(btn_del_part)
        p_btns.addWidget(btn_clear_parts)
        p_btns.addStretch()
        p_layout.addLayout(p_btns)
        splitter.addWidget(parts_box)

        # --- SECTION B: STOCK INVENTORY TABLE ---
        stock_box = QGroupBox("2. أطوال وخامات الاستوك المتاحة في المخزن (أعواد 12م/6م أو ألواح صاج)")
        stock_box.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        s_layout = QVBoxLayout(stock_box)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(6)
        self.stock_table.setHorizontalHeaderLabels([
            "كود الاستوك (Stock ID)", "القطاع / الخامة (Section)", "الرتبة (Grade)",
            "الطول (Length mm)", "العرض (Width mm)", "الكمية المتاحة (Qty)"
        ])
        self.stock_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        s_layout.addWidget(self.stock_table)

        # Stock action buttons
        s_btns = QHBoxLayout()
        btn_add_stock = QPushButton("+ إضافة خامة مخصصة")
        btn_add_stock.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        btn_add_stock.clicked.connect(self._add_empty_stock_row)

        btn_quick_12m = QPushButton("+ عود 12م سريع (عرض=0)")
        btn_quick_12m.setProperty("class", "secondaryBtn")
        btn_quick_12m.clicked.connect(lambda: self._add_preset_stock(12000.0, 0.0, "STK-12M"))

        btn_quick_6m = QPushButton("+ عود 6م سريع (عرض=0)")
        btn_quick_6m.setProperty("class", "secondaryBtn")
        btn_quick_6m.clicked.connect(lambda: self._add_preset_stock(6000.0, 0.0, "STK-6M"))

        btn_quick_plate = QPushButton("+ لوح صاج 2x6م سريع (عرض=2000)")
        btn_quick_plate.setProperty("class", "secondaryBtn")
        btn_quick_plate.clicked.connect(lambda: self._add_preset_stock(6000.0, 2000.0, "STK-PL2x6"))

        btn_del_stock = QPushButton("❌ حذف خامة")
        btn_del_stock.setProperty("class", "secondaryBtn")
        btn_del_stock.clicked.connect(self._delete_stock_row)

        btn_clear_stock = QPushButton("مسح الاستوك")
        btn_clear_stock.setProperty("class", "secondaryBtn")
        btn_clear_stock.clicked.connect(self._clear_stock)

        s_btns.addWidget(btn_add_stock)
        s_btns.addWidget(btn_quick_12m)
        s_btns.addWidget(btn_quick_6m)
        s_btns.addWidget(btn_quick_plate)
        s_btns.addWidget(btn_del_stock)
        s_btns.addWidget(btn_clear_stock)
        s_btns.addStretch()
        s_layout.addLayout(s_btns)
        splitter.addWidget(stock_box)

        splitter.setSizes([260, 240])
        layout.addWidget(splitter, 1)

        # 3. Bottom Controls: Modes & Cutting Rules & Run Button
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #1A212E;
                border: 1px solid #2D3748;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        c_layout = QHBoxLayout(controls_frame)
        c_layout.setContentsMargins(10, 6, 10, 6)
        c_layout.setSpacing(16)

        # Modes Group
        mode_box = QVBoxLayout()
        mode_box.setSpacing(4)
        lbl_mode_title = QLabel("طريقة النيستنج للكمرات (1D Mode):")
        lbl_mode_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_mode_title.setStyleSheet("color: #60A5FA;")
        mode_box.addWidget(lbl_mode_title)

        self.mode_group = QButtonGroup(self)
        self.rb_free = QRadioButton("وضع 1: أقل هالك (Free Nesting) — دمج حر لجميع المقاسات بالعود")
        self.rb_free.setChecked(True)
        self.rb_free.setToolTip("يسمح بدمج أي أطوال مختلفة في نفس العود للوصول إلى أقل نسبة هالك ممكنة.")

        self.rb_single = QRadioButton("وضع 2: مقاس طول واحد مكرر بالعود (Single Cut) — مثل 400، 400، 400...")
        self.rb_single.setToolTip("يحتوي كل عود على مقاس طول واحد فقط مكرر حتى استنفاد طول العود (ضبط مصدم المنشار مرة واحدة لكل عود).")

        self.rb_double = QRadioButton("وضع 3: مقاسين كحد أقصى بالعود (Double Cut) — دمج مقاسين مختلفين كحد أقصى")
        self.rb_double.setToolTip("يحتوي كل عود على مقاسين مختلفين كحد أقصى مكررين حسب الحاجة (ضبط مصدم المنشار مرتين كحد أقصى لكل عود).")

        self.mode_group.addButton(self.rb_free, 1)
        self.mode_group.addButton(self.rb_single, 2)
        self.mode_group.addButton(self.rb_double, 3)

        mode_box.addWidget(self.rb_free)
        mode_box.addWidget(self.rb_single)
        mode_box.addWidget(self.rb_double)
        c_layout.addLayout(mode_box, 3)

        # Parameters
        params_box = QVBoxLayout()
        params_box.setSpacing(6)
        lbl_params_title = QLabel("محددات المنشار وخلوص الصاج:")
        lbl_params_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_params_title.setStyleSheet("color: #94A3B8;")
        params_box.addWidget(lbl_params_title)

        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("سمك المنشار (Kerf):"))
        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0.0, 20.0)
        self.kerf_spin.setValue(3.0)
        self.kerf_spin.setSuffix(" mm")
        self.kerf_spin.setMaximumWidth(85)
        p_row.addWidget(self.kerf_spin)

        p_row.addWidget(QLabel("تهذيب الأطراف (Trim):"))
        self.trim_spin = QDoubleSpinBox()
        self.trim_spin.setRange(0.0, 100.0)
        self.trim_spin.setValue(15.0)
        self.trim_spin.setSuffix(" mm")
        self.trim_spin.setMaximumWidth(85)
        p_row.addWidget(self.trim_spin)

        p_row.addWidget(QLabel("خلوص الصاج (Margin):"))
        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(0.0, 100.0)
        self.margin_spin.setValue(10.0)
        self.margin_spin.setSuffix(" mm")
        self.margin_spin.setMaximumWidth(85)
        p_row.addWidget(self.margin_spin)

        params_box.addLayout(p_row)
        c_layout.addLayout(params_box, 4)

        # Big Run Button
        run_box = QVBoxLayout()
        run_box.setSpacing(4)
        self.btn_run = QPushButton("⚡ ابدأ التحسين والتقطيع فوراً\nStart Optimization")
        self.btn_run.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                min-height: 52px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
            }
        """)
        self.btn_run.clicked.connect(self._run_optimization)
        run_box.addWidget(self.btn_run)
        c_layout.addLayout(run_box, 2)

        layout.addWidget(controls_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #60A5FA; font-weight: bold;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.progress_bar)

    def load_project_data(self, project_id: str):
        self.active_project_id = project_id
        # Load 1D Parts
        parts_1d = self.cut_repo.list_linear_by_project(project_id)
        # Load 2D Parts
        parts_2d = self.cut_repo.list_plate_by_project(project_id)

        total_parts = len(parts_1d) + len(parts_2d)
        self.parts_table.setRowCount(total_parts)

        row = 0
        for p in parts_1d:
            self._set_part_row(row, p.mark, p.designation, p.grade, p.length_mm, 0.0, p.quantity, False, p.id)
            row += 1
        for p in parts_2d:
            self._set_part_row(row, p.mark, f"PL {p.thickness_mm:.0f}mm", p.grade, p.length_mm, p.width_mm, p.quantity, p.allow_rotation, p.id)
            row += 1

        # Load Stock
        stock = self.stock_repo.list_all()
        self.stock_table.setRowCount(len(stock))
        for row, s in enumerate(stock):
            self._set_stock_row(row, s.id, s.designation, s.grade, s.length_mm, s.width_mm, s.available_qty - s.used_qty)

    def _set_part_row(self, row: int, mark: str, section: str, grade: str, length: float, width: float, qty: int, allow_rot: bool, pid: str = ""):
        self.parts_table.blockSignals(True)
        self.parts_table.setItem(row, 0, QTableWidgetItem(mark))
        self.parts_table.setItem(row, 1, QTableWidgetItem(section))
        self.parts_table.setItem(row, 2, QTableWidgetItem(grade))
        self.parts_table.setItem(row, 3, QTableWidgetItem(str(int(length) if length.is_integer() else length)))
        
        # Width: highlight if 2D plate (>0)
        w_item = QTableWidgetItem(str(int(width) if width.is_integer() else width))
        if width > 0:
            w_item.setForeground(QColor("#A78BFA"))  # Light purple for plates
        self.parts_table.setItem(row, 4, w_item)

        self.parts_table.setItem(row, 5, QTableWidgetItem(str(qty)))
        self.parts_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, pid or str(uuid.uuid4()))
        self.parts_table.blockSignals(False)

        # Configure interactive rotation button in column 6
        self._configure_rotation_cell(row, width > 0, allow_rot)

    def _configure_rotation_cell(self, row: int, is_plate: bool, allow_rot: bool):
        if not is_plate:
            btn = QPushButton("— (كمرة)")
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #64748B;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 3px;
                }
            """)
            self.parts_table.setCellWidget(row, 6, btn)
        else:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._set_rotate_btn_state(btn, allow_rot)
            btn.clicked.connect(lambda checked, b=btn: self._toggle_rotate_button(b))
            self.parts_table.setCellWidget(row, 6, btn)

    def _set_rotate_btn_state(self, btn: QPushButton, state: bool):
        btn.setProperty("allow_rotation", state)
        if state:
            btn.setText("✔ نعم (مسموح بالدوران)")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #FFFFFF;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 11px;
                    border: 1px solid #10B981;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
        else:
            btn.setText("✖ لا (اتجاه ثابت)")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #475569;
                    color: #E2E8F0;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 11px;
                    border: 1px solid #64748B;
                }
                QPushButton:hover {
                    background-color: #334155;
                }
            """)

    def _toggle_rotate_button(self, btn: QPushButton):
        curr = bool(btn.property("allow_rotation"))
        self._set_rotate_btn_state(btn, not curr)

    def _on_part_cell_changed(self, row: int, col: int):
        if col == 4:  # Width column changed
            item = self.parts_table.item(row, col)
            if not item:
                return
            try:
                w_val = float(item.text().strip())
                curr_widget = self.parts_table.cellWidget(row, 6)
                is_currently_plate = curr_widget and curr_widget.isEnabled() if curr_widget else False
                if (w_val > 0) != is_currently_plate:
                    self._configure_rotation_cell(row, w_val > 0, True)
            except ValueError:
                pass

    def _set_stock_row(self, row: int, sid: str, section: str, grade: str, length: float, width: float, qty: int, cost: float = 0.0):
        self.stock_table.setItem(row, 0, QTableWidgetItem(sid))
        self.stock_table.setItem(row, 1, QTableWidgetItem(section))
        self.stock_table.setItem(row, 2, QTableWidgetItem(grade))
        self.stock_table.setItem(row, 3, QTableWidgetItem(str(int(length) if length.is_integer() else length)))
        
        w_item = QTableWidgetItem(str(int(width) if width.is_integer() else width))
        if width > 0:
            w_item.setForeground(QColor("#A78BFA"))
        self.stock_table.setItem(row, 4, w_item)

        self.stock_table.setItem(row, 5, QTableWidgetItem(str(qty)))
        self.stock_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, sid)

    def _add_beam_row(self):
        row = self.parts_table.rowCount()
        self.parts_table.insertRow(row)
        prev_sec = self.parts_table.item(row - 1, 1).text() if row > 0 and self.parts_table.item(row - 1, 1) else "IPE 300"
        prev_grd = self.parts_table.item(row - 1, 2).text() if row > 0 and self.parts_table.item(row - 1, 2) else "S355JR"
        self._set_part_row(row, f"B-{row + 1}", prev_sec, prev_grd, 4500.0, 0.0, 1, False)

    def _add_plate_row(self):
        row = self.parts_table.rowCount()
        self.parts_table.insertRow(row)
        self._set_part_row(row, f"PL-{row + 1}", "PL 12mm", "S275JR", 500.0, 350.0, 2, True)

    def _delete_part_row(self):
        row = self.parts_table.currentRow()
        if row >= 0:
            self.parts_table.removeRow(row)

    def _clear_parts(self):
        self.parts_table.setRowCount(0)

    def _add_empty_stock_row(self):
        row = self.stock_table.rowCount()
        self.stock_table.insertRow(row)
        self._set_stock_row(row, f"STK-{uuid.uuid4().hex[:4].upper()}", "IPE 300", "S355JR", 12000.0, 0.0, 10)

    def _add_preset_stock(self, length_val: float, width_val: float, prefix: str):
        row = self.stock_table.rowCount()
        self.stock_table.insertRow(row)
        if width_val > 0:
            self._set_stock_row(row, f"{prefix}-{row+1}", "PL 12mm", "S275JR", length_val, width_val, 6)
        else:
            first_sec = self.parts_table.item(0, 1).text() if self.parts_table.rowCount() > 0 and self.parts_table.item(0, 1) else "IPE 300"
            first_grd = self.parts_table.item(0, 2).text() if self.parts_table.rowCount() > 0 and self.parts_table.item(0, 2) else "S355JR"
            self._set_stock_row(row, f"{prefix}-{first_sec.replace(' ', '')}", first_sec, first_grd, length_val, 0.0, 20)

    def _delete_stock_row(self):
        row = self.stock_table.currentRow()
        if row >= 0:
            self.stock_table.removeRow(row)

    def _clear_stock(self):
        self.stock_table.setRowCount(0)

    def _load_demo_data(self):
        """Loads both linear beams (Width=0) and 2D plates (Width>0) into the same screen."""
        self.parts_table.setRowCount(0)
        demo_parts = [
            # 1D Linear Beams (Width = 0)
            ("B-101", "IPE 300", "S355JR", 5400.0, 0.0, 4, False),
            ("B-102", "IPE 300", "S355JR", 6200.0, 0.0, 6, False),
            ("C-201", "IPE 300", "S355JR", 4500.0, 0.0, 5, False),
            # 2D Steel Plates (Width > 0)
            ("BP-1", "PL 12mm", "S275JR", 600.0, 400.0, 8, True),
            ("GUS-1", "PL 12mm", "S275JR", 350.0, 250.0, 12, True)
        ]
        self.parts_table.setRowCount(len(demo_parts))
        for r, (mk, sec, grd, l, w, q, rot) in enumerate(demo_parts):
            self._set_part_row(r, mk, sec, grd, l, w, q, rot)

        self.stock_table.setRowCount(0)
        demo_stock = [
            ("STK-IPE300-12M", "IPE 300", "S355JR", 12000.0, 0.0, 20),
            ("STK-IPE300-6M", "IPE 300", "S355JR", 6000.0, 0.0, 10),
            ("STK-PL12-2x6", "PL 12mm", "S275JR", 6000.0, 2000.0, 5)
        ]
        self.stock_table.setRowCount(len(demo_stock))
        for r, (sid, sec, grd, l, w, q) in enumerate(demo_stock):
            self._set_stock_row(r, sid, sec, grd, l, w, q)

        QMessageBox.information(
            self, "تم تحميل النموذج الشامل",
            "تم تحميل نموذج كمرات (عرض=0) وألواح صاج (عرض>0) واستوك متكامل بنجاح!\nاضغط الآن على 'ابدأ التحسين والتقطيع فوراً'."
        )

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "استيراد ملف إكسيل للقطع", "", "Excel / CSV Files (*.xlsx *.csv)")
        if not path:
            return
        parts_1d, parts_2d, errs = ExcelDataImporter.import_unified_cut_list(path)
        total_count = len(parts_1d) + len(parts_2d)
        if total_count == 0:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على قطع صالحة بالملف.")
            return

        curr_rows = self.parts_table.rowCount()
        self.parts_table.setRowCount(curr_rows + total_count)

        # Insert linear items
        idx = 0
        for p in parts_1d:
            self._set_part_row(curr_rows + idx, p.mark, p.designation, p.grade, p.length_mm, 0.0, p.quantity, False, p.id)
            idx += 1

        # Insert plate items
        for pl in parts_2d:
            sec_name = f"PL {int(pl.thickness_mm) if pl.thickness_mm.is_integer() else pl.thickness_mm}mm"
            self._set_part_row(curr_rows + idx, pl.mark, sec_name, pl.grade, pl.length_mm, pl.width_mm, pl.quantity, pl.allow_rotation, pl.id)
            idx += 1

        msg = f"تم استيراد {len(parts_1d)} قطعة كمرات و {len(parts_2d)} قطعة صاج/بليت بنجاح ({total_count} إجمالي)."
        if errs:
            msg += "\n\nملاحظات:\n" + "\n".join(errs[:3])
        QMessageBox.information(self, "نتيجة الاستيراد", msg)

    def _download_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ نموذج الإكسيل", "SteelNest_CutList_Template.xlsx", "Excel Files (*.xlsx)")
        if path:
            TemplateGenerator.generate_unified_cut_list_template(path)
            QMessageBox.information(
                self, "تم الحفظ",
                f"تم حفظ نموذج إكسيل شامل للكمرات وألواح وبليتات الصاج بنجاح في:\n{path}\n\nيمكنك تعبئته واستيراده مباشرة!"
            )

    def _collect_data(self):
        """Separates rows into 1D linear items (Width=0) and 2D plate items (Width>0)."""
        parts_1d: list[PartCutItem] = []
        parts_2d: list[PlatePartItem] = []

        for r in range(self.parts_table.rowCount()):
            try:
                mk = self.parts_table.item(r, 0).text().strip() if self.parts_table.item(r, 0) else f"P{r+1}"
                sec = self.parts_table.item(r, 1).text().strip() if self.parts_table.item(r, 1) else ""
                grd = self.parts_table.item(r, 2).text().strip() if self.parts_table.item(r, 2) else "S355JR"
                l_str = self.parts_table.item(r, 3).text().strip() if self.parts_table.item(r, 3) else "0"
                w_str = self.parts_table.item(r, 4).text().strip() if self.parts_table.item(r, 4) else "0"
                q_str = self.parts_table.item(r, 5).text().strip() if self.parts_table.item(r, 5) else "1"
                length_val = float(l_str)
                width_val = float(w_str)
                qty_val = int(float(q_str))

                # Read rotation from interactive button widget or item fallback
                btn = self.parts_table.cellWidget(r, 6)
                if btn and isinstance(btn, QPushButton) and btn.isEnabled():
                    allow_rot = bool(btn.property("allow_rotation"))
                else:
                    rot_item = self.parts_table.item(r, 6)
                    rot_str = rot_item.text().strip() if rot_item else "نعم"
                    allow_rot = "نعم" in rot_str or "yes" in rot_str.lower() or rot_str == "1"

                if length_val <= 0 or qty_val <= 0 or not sec:
                    continue

                pid = self.parts_table.item(r, 0).data(Qt.ItemDataRole.UserRole) or str(uuid.uuid4())

                if width_val <= 0:
                    # 1D Linear Part
                    parts_1d.append(PartCutItem(
                        id=pid, mark=mk, designation=sec, grade=grd,
                        length_mm=length_val, quantity=qty_val
                    ))
                else:
                    # 2D Plate Part
                    # Extract thickness if designation is like PL 12mm
                    thk = 10.0
                    import re
                    match = re.search(r"(\d+(?:\.\d+)?)", sec)
                    if match:
                        try:
                            thk = float(match.group(1))
                        except ValueError:
                            pass
                    parts_2d.append(PlatePartItem(
                        id=pid, mark=mk, thickness_mm=thk, grade=grd,
                        width_mm=width_val, length_mm=length_val,
                        quantity=qty_val, allow_rotation=allow_rot
                    ))
            except Exception:
                continue

        # Collect Stock (No cost column)
        stock_items: list[StockItem] = []
        for r in range(self.stock_table.rowCount()):
            try:
                sid = self.stock_table.item(r, 0).text().strip() if self.stock_table.item(r, 0) else f"STK-{r+1}"
                sec = self.stock_table.item(r, 1).text().strip() if self.stock_table.item(r, 1) else ""
                grd = self.stock_table.item(r, 2).text().strip() if self.stock_table.item(r, 2) else "S355JR"
                l_str = self.stock_table.item(r, 3).text().strip() if self.stock_table.item(r, 3) else "0"
                w_str = self.stock_table.item(r, 4).text().strip() if self.stock_table.item(r, 4) else "0"
                q_str = self.stock_table.item(r, 5).text().strip() if self.stock_table.item(r, 5) else "1"

                length_val = float(l_str)
                width_val = float(w_str)
                qty_val = int(float(q_str))

                if length_val <= 0 or qty_val <= 0 or not sec:
                    continue

                mtype = MaterialType.PLATE if width_val > 0 else MaterialType.LINEAR
                thk = 0.0
                if width_val > 0:
                    import re
                    match = re.search(r"(\d+(?:\.\d+)?)", sec)
                    if match:
                        try:
                            thk = float(match.group(1))
                        except ValueError:
                            pass

                stock_items.append(StockItem(
                    id=sid, designation=sec, grade=grd,
                    length_mm=length_val, width_mm=width_val, thickness_mm=thk,
                    available_qty=qty_val, cost_per_unit=0.0,
                    material_type=mtype
                ))
            except Exception:
                continue

        return parts_1d, parts_2d, stock_items

    def _run_optimization(self):
        parts_1d, parts_2d, stock_items = self._collect_data()

        if not parts_1d and not parts_2d:
            QMessageBox.warning(self, "بيانات ناقصة", "يرجى إدخال القطع المطلوب تفصيلها في الجدول الأول.")
            return

        if not stock_items:
            QMessageBox.warning(self, "استوك ناقص", "يرجى إدخال أطوال الاستوك المتاحة في المخزن في الجدول الثاني، أو الضغط على زر '+ عود 12م سريع'.")
            return

        # Determine 1D mode
        if self.rb_single.isChecked():
            mode = LinearOptimizationMode.SINGLE_CUT
        elif self.rb_double.isChecked():
            mode = LinearOptimizationMode.DOUBLE_CUT
        else:
            mode = LinearOptimizationMode.FREE_NESTING

        settings = ProjectSettings(
            kerf_mm=self.kerf_spin.value(),
            trim_start_mm=self.trim_spin.value(),
            trim_end_mm=self.trim_spin.value(),
            plate_kerf_mm=self.kerf_spin.value(),
            plate_margin_mm=self.margin_spin.value(),
            min_remnant_length_mm=500.0,
            linear_mode=mode,
            time_limit_sec=20
        )

        # Sync to DB if active project
        if self.active_project_id:
            self.cut_repo.clear_linear(self.active_project_id)
            self.cut_repo.clear_plate(self.active_project_id)
            for p in parts_1d:
                self.cut_repo.add_linear(p, self.active_project_id)
            for p in parts_2d:
                self.cut_repo.add_plate(p, self.active_project_id)
            for s in stock_items:
                self.stock_repo.add(s)

        self.btn_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText("جاري حساب توزيعة التقطيع (1D كمـرات + 2D ألواح صـاج)...")

        self.worker = OptimizationWorker(
            mode_type="AUTO",
            settings=settings,
            parts_1d=parts_1d,
            parts_2d=parts_2d,
            stock=stock_items,
            project_id=self.active_project_id or "QUICK-PRJ",
            parent=self
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_finished(self, result: OptimizationResult):
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        self.optimization_finished.emit(result)

    def _on_error(self, err: str):
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        QMessageBox.critical(self, "خطأ في التحسين", f"حدث خطأ أثناء الحساب:\n{err}")
