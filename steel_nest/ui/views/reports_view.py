"""
Excel Reports View
Generates the comprehensive 8-sheet engineering Excel workbook.
"""
import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from steel_nest.models.nesting_plan import OptimizationResult
from steel_nest.database.repositories import (
    ProjectRepository, CutListRepository, StockRepository, RemnantRepository
)
from steel_nest.reporting.excel_exporter import ExcelReportExporter

class ReportsView(QWidget):
    def __init__(
        self,
        project_repo: ProjectRepository,
        cut_repo: CutListRepository,
        stock_repo: StockRepository,
        remnant_repo: RemnantRepository,
        parent=None
    ):
        super().__init__(parent)
        self.project_repo = project_repo
        self.cut_repo = cut_repo
        self.stock_repo = stock_repo
        self.remnant_repo = remnant_repo
        self.active_project_id = None
        self.last_result: OptimizationResult = None
        self.last_exported_file = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title_box = QVBoxLayout()
        h_title = QLabel("Professional Excel Reports")
        h_title.setObjectName("viewTitle")
        self.sub_title = QLabel("Generate multi-sheet engineering Excel workbooks compliant with structural fabrication standards.")
        self.sub_title.setObjectName("viewSubtitle")
        title_box.addWidget(h_title)
        title_box.addWidget(self.sub_title)
        layout.addLayout(title_box)

        # Info Card explaining the 8 Sheets
        card = QFrame()
        card.setProperty("class", "card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(8)

        lbl_sheets = QLabel("Included Worksheets in Production Workbook:")
        lbl_sheets.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        c_layout.addWidget(lbl_sheets)

        sheets_info = [
            ("Sheet 1: Executive Summary", "Project KPIs, total lengths/areas, utilization %, scrap %, estimated purchasing cost."),
            ("Sheet 2: Detailed Cutting Plan", "Bar-by-bar sequence, part marks, kerfs, trims, used length, and offcut classification."),
            ("Sheet 3: Cut List", "Part marks, required vs nested quantities, cutting status (Completed/Partial/Unassigned)."),
            ("Sheet 4: Stock Purchase List", "Required raw stock vs available warehouse inventory, identifying purchase quantities."),
            ("Sheet 5: Remnants and Offcuts", "Tracking of usable offcuts with IDs, dimensions, and storage rack references."),
            ("Sheet 6: Material Summary", "Aggregated quantities, total weights, and utilization grouped by section and grade."),
            ("Sheet 7: Plate Nesting", "2D layout breakdown, stock plate sizes, positioned part marks, and area metrics."),
            ("Sheet 8: Unprocessed Exceptions", "Complete audit trail of infeasible parts with clear engineering failure reasons.")
        ]

        for s_title, s_desc in sheets_info:
            row_lbl = QLabel(f"<b>{s_title}</b> — <span style='color: #94A3B8;'>{s_desc}</span>")
            c_layout.addWidget(row_lbl)

        layout.addWidget(card)

        # Status & Action Buttons
        self.status_lbl = QLabel("No nesting run available to export yet. Please execute linear or plate nesting first.")
        self.status_lbl.setStyleSheet("color: #F59E0B; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.btn_export = QPushButton("📊 Generate & Save 8-Sheet Excel Workbook")
        self.btn_export.setProperty("class", "primaryBtn")
        self.btn_export.setMinimumHeight(42)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_excel)

        self.btn_open = QPushButton("Open in Microsoft Excel")
        self.btn_open.setProperty("class", "secondaryBtn")
        self.btn_open.setMinimumHeight(42)
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_in_excel)

        btn_row.addWidget(self.btn_export, 2)
        btn_row.addWidget(self.btn_open, 1)
        layout.addLayout(btn_row)

        layout.addStretch()

    def set_active_project(self, project_id: str):
        self.active_project_id = project_id
        proj = self.project_repo.get(project_id)
        if proj:
            self.sub_title.setText(f"Project: {proj.name} ({proj.code})")

    def set_result(self, result: OptimizationResult):
        self.last_result = result
        self.btn_export.setEnabled(True)
        self.status_lbl.setText(f"Ready to export nesting results for mode '{result.mode}' ({result.total_parts_nested} parts nested).")
        self.status_lbl.setStyleSheet("color: #10B981; font-weight: bold;")

    def _export_excel(self):
        if not self.last_result:
            QMessageBox.warning(self, "No Results", "No nesting results available to export.")
            return

        proj = self.project_repo.get(self.active_project_id)
        if not proj:
            from steel_nest.models.project import Project
            proj = Project(id="TEMP", name="Nesting Project", code="PRJ-01")

        default_filename = f"SteelNest_{proj.code}_{self.last_result.mode}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel Workbook", default_filename, "Excel Files (*.xlsx)")
        if not path:
            return

        parts_1d = self.cut_repo.list_linear_by_project(self.active_project_id) if self.active_project_id else []
        parts_2d = self.cut_repo.list_plate_by_project(self.active_project_id) if self.active_project_id else []
        stock = self.stock_repo.list_all()
        remnants = self.remnant_repo.list_all()

        try:
            ExcelReportExporter.export_full_workbook(
                file_path=path,
                project=proj,
                result=self.last_result,
                parts_1d=parts_1d,
                parts_2d=parts_2d,
                stock_items=stock,
                remnants=remnants
            )
            self.last_exported_file = path
            self.btn_open.setEnabled(True)
            QMessageBox.information(self, "Export Successful", f"Professional Excel report generated successfully:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to generate Excel report:\n{str(e)}")

    def _open_in_excel(self):
        if self.last_exported_file and os.path.exists(self.last_exported_file):
            try:
                os.startfile(self.last_exported_file)
            except Exception as e:
                QMessageBox.warning(self, "Open File", f"Could not launch Excel directly: {str(e)}")
