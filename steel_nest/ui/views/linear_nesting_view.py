"""
1D Linear Nesting Configuration & Execution View
Provides selection of Mode 1 (Free), Mode 2 (Single Cut), Mode 3 (Double Cut),
and 3-mode comparative evaluation.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QGroupBox, QFormLayout,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QProgressBar,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal

from steel_nest.config import LinearOptimizationMode, NestingObjective
from steel_nest.database.repositories import CutListRepository, StockRepository, ProjectRepository
from steel_nest.models.project import ProjectSettings
from steel_nest.ui.workers.optimization_worker import OptimizationWorker
from steel_nest.models.nesting_plan import OptimizationResult

class LinearNestingView(QWidget):
    optimization_finished = pyqtSignal(object) # OptimizationResult

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
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title_box = QVBoxLayout()
        h_title = QLabel("1D Linear Cutting Stock Optimization")
        h_title.setObjectName("viewTitle")
        self.sub_title = QLabel("Select nesting mode, configure machine saw allowances, and execute mathematical solver.")
        self.sub_title.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(self.sub_title)
        layout.addLayout(title_box)

        # MODE SELECTION GROUP (Essential Master Requirement)
        mode_group = QGroupBox("Nesting Mode Selection (Required)")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(12)

        self.btn_group_mode = QButtonGroup(self)

        self.rb_mode1 = QRadioButton("Mode 1: Free Nesting — Minimum Material Waste (Multi-cut per bar)")
        self.rb_mode1.setChecked(True)
        self.rb_mode1.setStyleSheet("font-weight: bold; color: #60A5FA;")
        lbl_desc1 = QLabel("   • Combines multiple cut lengths on each stock bar to achieve maximum material utilization.\n   • Solves cutting stock problem via OR-Tools CP-SAT and heuristic packing.")
        lbl_desc1.setStyleSheet("color: #94A3B8; font-size: 11px;")

        self.rb_mode2 = QRadioButton("Mode 2: Single Cut per Stock Bar (Strictly ONE part per bar)")
        self.rb_mode2.setStyleSheet("font-weight: bold; color: #F59E0B;")
        lbl_desc2 = QLabel("   • Strictly restricts each stock bar to containing exactly one finished piece.\n   • Does NOT combine cuts; reports full remaining bar length as remnant/waste.")
        lbl_desc2.setStyleSheet("color: #94A3B8; font-size: 11px;")

        self.rb_mode3 = QRadioButton("Mode 3: Double Cuts per Stock Bar (Maximum TWO parts per bar)")
        self.rb_mode3.setStyleSheet("font-weight: bold; color: #10B981;")
        lbl_desc3 = QLabel("   • Optimizes pairwise combinations with at most two finished cut pieces on each bar.\n   • Never places 3 or more pieces on a single bar.")
        lbl_desc3.setStyleSheet("color: #94A3B8; font-size: 11px;")

        self.btn_group_mode.addButton(self.rb_mode1, 1)
        self.btn_group_mode.addButton(self.rb_mode2, 2)
        self.btn_group_mode.addButton(self.rb_mode3, 3)

        mode_layout.addWidget(self.rb_mode1)
        mode_layout.addWidget(lbl_desc1)
        mode_layout.addWidget(self.rb_mode2)
        mode_layout.addWidget(lbl_desc2)
        mode_layout.addWidget(self.rb_mode3)
        mode_layout.addWidget(lbl_desc3)
        layout.addWidget(mode_group)

        # Advanced Cutting Parameters Row
        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        rules_box = QGroupBox("Saw Blade & Trimming Rules")
        r_form = QFormLayout(rules_box)

        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0.0, 20.0)
        self.kerf_spin.setValue(3.0)
        self.kerf_spin.setSuffix(" mm")

        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0.0, 100.0)
        self.trim_start_spin.setValue(15.0)
        self.trim_start_spin.setSuffix(" mm")

        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0.0, 100.0)
        self.trim_end_spin.setValue(15.0)
        self.trim_end_spin.setSuffix(" mm")

        self.min_remnant_spin = QDoubleSpinBox()
        self.min_remnant_spin.setRange(0.0, 5000.0)
        self.min_remnant_spin.setValue(500.0)
        self.min_remnant_spin.setSuffix(" mm")

        r_form.addRow("Saw Blade Kerf:", self.kerf_spin)
        r_form.addRow("Start Trimming Allowance:", self.trim_start_spin)
        r_form.addRow("End Trimming Allowance:", self.trim_end_spin)
        r_form.addRow("Min. Reusable Remnant Length:", self.min_remnant_spin)
        params_row.addWidget(rules_box)

        solver_box = QGroupBox("Solver Strategy & Objectives")
        s_form = QFormLayout(solver_box)

        self.obj_combo = QComboBox()
        self.obj_combo.addItem("Minimum Waste Length", NestingObjective.MIN_WASTE)
        self.obj_combo.addItem("Minimum Number of Stock Bars", NestingObjective.MIN_BARS)
        self.obj_combo.addItem("Minimum Material Purchasing Cost", NestingObjective.MIN_COST)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 300)
        self.time_spin.setValue(30)
        self.time_spin.setSuffix(" sec")

        self.check_remnants = QCheckBox("Prioritize Reusable Remnants from Inventory")
        self.check_remnants.setChecked(True)

        s_form.addRow("Optimization Objective:", self.obj_combo)
        s_form.addRow("Time Limit:", self.time_spin)
        s_form.addRow("", self.check_remnants)
        params_row.addWidget(solver_box)

        layout.addLayout(params_row)

        # Progress Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #60A5FA; font-weight: bold;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.progress_bar)

        # Execution Buttons Row
        exec_row = QHBoxLayout()
        self.btn_run = QPushButton("⚡ Run Linear Nesting Optimization")
        self.btn_run.setProperty("class", "primaryBtn")
        self.btn_run.setMinimumHeight(38)
        self.btn_run.clicked.connect(self._run_optimization)

        self.btn_compare = QPushButton("📊 Compare All 3 Modes Side-by-Side")
        self.btn_compare.setProperty("class", "secondaryBtn")
        self.btn_compare.setMinimumHeight(38)
        self.btn_compare.clicked.connect(self._run_mode_comparison)

        exec_row.addWidget(self.btn_run, 2)
        exec_row.addWidget(self.btn_compare, 1)
        layout.addLayout(exec_row)

        # Comparison Results Display Table (Optional / Collapsible)
        self.compare_table = QTableWidget()
        self.compare_table.setColumnCount(6)
        self.compare_table.setHorizontalHeaderLabels([
            "Optimization Mode", "Bars Required", "Total Parts Len (m)",
            "Total Material (m)", "Remnants (m)", "Overall Utilization %"
        ])
        self.compare_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.compare_table.setVisible(False)
        layout.addWidget(self.compare_table)

    def set_active_project(self, project_id: str):
        self.active_project_id = project_id
        proj = self.project_repo.get(project_id)
        if proj:
            self.sub_title.setText(f"Active Project: {proj.name} ({proj.code})")
            self.kerf_spin.setValue(proj.settings.kerf_mm)
            self.trim_start_spin.setValue(proj.settings.trim_start_mm)
            self.trim_end_spin.setValue(proj.settings.trim_end_mm)
            self.min_remnant_spin.setValue(proj.settings.min_remnant_length_mm)

    def _get_current_mode(self) -> LinearOptimizationMode:
        if self.rb_mode2.isChecked():
            return LinearOptimizationMode.SINGLE_CUT
        elif self.rb_mode3.isChecked():
            return LinearOptimizationMode.DOUBLE_CUT
        return LinearOptimizationMode.FREE_NESTING

    def _run_optimization(self):
        if not self.active_project_id:
            QMessageBox.information(self, "No Active Project", "Please select or create an active project first.")
            return

        parts = self.cut_repo.list_linear_by_project(self.active_project_id)
        if not parts:
            QMessageBox.warning(self, "No Parts", "No linear cut parts found in active project. Please add or import parts.")
            return

        stock = self.stock_repo.list_all()
        if not stock:
            QMessageBox.warning(self, "No Stock", "No stock items available in inventory. Please seed demo stock or add inventory.")
            return

        mode = self._get_current_mode()
        settings = ProjectSettings(
            kerf_mm=self.kerf_spin.value(),
            trim_start_mm=self.trim_start_spin.value(),
            trim_end_mm=self.trim_end_spin.value(),
            min_remnant_length_mm=self.min_remnant_spin.value(),
            linear_mode=mode,
            objective=self.obj_combo.currentData(),
            time_limit_sec=self.time_spin.value(),
            allow_remnants_use=self.check_remnants.isChecked()
        )

        self.btn_run.setEnabled(False)
        self.btn_compare.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText("Starting optimization...")
        self.compare_table.setVisible(False)

        self.worker = OptimizationWorker(
            mode_type="LINEAR",
            settings=settings,
            parts_1d=parts,
            parts_2d=[],
            stock=stock,
            project_id=self.active_project_id,
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
        self.btn_compare.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        self.optimization_finished.emit(result)

    def _on_error(self, err_msg: str):
        self.btn_run.setEnabled(True)
        self.btn_compare.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        QMessageBox.critical(self, "Optimization Error", f"Solver encountered an error:\n{err_msg}")

    def _run_mode_comparison(self):
        if not self.active_project_id:
            QMessageBox.information(self, "No Active Project", "Please select a project.")
            return
        parts = self.cut_repo.list_linear_by_project(self.active_project_id)
        stock = self.stock_repo.list_all()
        if not parts or not stock:
            QMessageBox.warning(self, "Missing Data", "Cut list or stock inventory is empty.")
            return

        from steel_nest.core.linear_optimizer import LinearOptimizer

        modes = [
            ("Mode 1: Free Nesting", LinearOptimizationMode.FREE_NESTING),
            ("Mode 2: Single Cut / Bar", LinearOptimizationMode.SINGLE_CUT),
            ("Mode 3: Double Cuts / Bar", LinearOptimizationMode.DOUBLE_CUT),
        ]

        self.compare_table.setRowCount(len(modes))
        self.compare_table.setVisible(True)

        for row, (label, mode) in enumerate(modes):
            opt = LinearOptimizer(
                mode=mode,
                objective=self.obj_combo.currentData(),
                kerf_mm=self.kerf_spin.value(),
                trim_start_mm=self.trim_start_spin.value(),
                trim_end_mm=self.trim_end_spin.value(),
                min_remnant_length_mm=self.min_remnant_spin.value(),
                time_limit_sec=10,
                allow_remnants_use=self.check_remnants.isChecked()
            )
            res = opt.optimize(parts, stock, self.active_project_id)
            self.compare_table.setItem(row, 0, QTableWidgetItem(label))
            self.compare_table.setItem(row, 1, QTableWidgetItem(f"{res.total_stock_used} bars"))
            self.compare_table.setItem(row, 2, QTableWidgetItem(f"{res.total_parts_length_m:.2f} m"))
            self.compare_table.setItem(row, 3, QTableWidgetItem(f"{res.total_material_length_m:.2f} m"))
            self.compare_table.setItem(row, 4, QTableWidgetItem(f"{res.total_reusable_remnants_length_m:.2f} m"))
            
            c_util = QTableWidgetItem(f"{res.overall_utilization_pct:.1f}%")
            if res.overall_utilization_pct >= 90.0:
                c_util.setForeground(Qt.GlobalColor.green)
            self.compare_table.setItem(row, 5, c_util)
