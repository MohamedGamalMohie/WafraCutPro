"""
2D Rectangular Plate Nesting View
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from steel_nest.database.repositories import CutListRepository, StockRepository, ProjectRepository
from steel_nest.models.project import ProjectSettings
from steel_nest.ui.workers.optimization_worker import OptimizationWorker
from steel_nest.models.nesting_plan import OptimizationResult

class PlateNestingView(QWidget):
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
        h_title = QLabel("2D Rectangular Plate Nesting")
        h_title.setObjectName("viewTitle")
        self.sub_title = QLabel("Optimize 2D sheet & plate cut plans with rotation, cutting kerf, and margin constraints.")
        self.sub_title.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(self.sub_title)
        layout.addLayout(title_box)

        # Parameters Group
        params_box = QGroupBox("Plate Cutting & Geometry Parameters")
        form = QFormLayout(params_box)

        self.kerf_spin = QDoubleSpinBox()
        self.kerf_spin.setRange(0.0, 30.0)
        self.kerf_spin.setValue(4.0)
        self.kerf_spin.setSuffix(" mm")

        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(0.0, 100.0)
        self.margin_spin.setValue(10.0)
        self.margin_spin.setSuffix(" mm")

        self.check_guillotine = QCheckBox("Enforce Guillotine Straight Cuts Only (Shearing Machine)")
        self.check_guillotine.setChecked(False)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 300)
        self.time_spin.setValue(30)
        self.time_spin.setSuffix(" sec")

        form.addRow("Plasma / Flame / Laser Kerf:", self.kerf_spin)
        form.addRow("Plate Edge Safety Margin:", self.margin_spin)
        form.addRow("Cutting Machine Constraints:", self.check_guillotine)
        form.addRow("Optimization Time Limit:", self.time_spin)
        layout.addWidget(params_box)

        # Progress Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #60A5FA; font-weight: bold;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.progress_bar)

        # Run Button
        self.btn_run = QPushButton("⚡ Run 2D Plate Nesting Engine")
        self.btn_run.setProperty("class", "primaryBtn")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self._run_plate_nesting)
        layout.addWidget(self.btn_run)

        layout.addStretch()

    def set_active_project(self, project_id: str):
        self.active_project_id = project_id
        proj = self.project_repo.get(project_id)
        if proj:
            self.sub_title.setText(f"Active Project: {proj.name} ({proj.code})")

    def _run_plate_nesting(self):
        if not self.active_project_id:
            QMessageBox.information(self, "No Project", "Please select an active project.")
            return

        parts = self.cut_repo.list_plate_by_project(self.active_project_id)
        if not parts:
            QMessageBox.warning(self, "No Plate Parts", "No plate requirements found. Please add or import plate parts in Cut List.")
            return

        stock = self.stock_repo.list_all()
        if not stock:
            QMessageBox.warning(self, "No Stock", "No stock plates available. Please seed or add stock plates in Inventory.")
            return

        settings = ProjectSettings(
            plate_kerf_mm=self.kerf_spin.value(),
            plate_margin_mm=self.margin_spin.value(),
            guillotine_cuts_only=self.check_guillotine.isChecked(),
            time_limit_sec=self.time_spin.value()
        )

        self.btn_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText("Running 2D plate optimizer...")

        self.worker = OptimizationWorker(
            mode_type="PLATE",
            settings=settings,
            parts_1d=[],
            parts_2d=parts,
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
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        self.optimization_finished.emit(result)

    def _on_error(self, err: str):
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setVisible(False)
        QMessageBox.critical(self, "Error", f"Plate solver failed:\n{err}")
