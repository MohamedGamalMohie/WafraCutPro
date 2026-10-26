"""
Visual Nesting Results View
Displays scaled graphical cutting bars and 2D plate layouts with detailed breakdown.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from steel_nest.models.nesting_plan import OptimizationResult
from steel_nest.ui.widgets.bar_visualizer import BarVisualizerWidget
from steel_nest.ui.widgets.plate_visualizer import PlateVisualizerWidget
from steel_nest.ui.widgets.kpi_card import KPICard
from steel_nest.core.remnant_manager import RemnantManager
from steel_nest.database.repositories import RemnantRepository, StockRepository, ProjectRepository
from steel_nest.reporting.excel_exporter import ExcelReportExporter

class ResultsView(QWidget):
    export_excel_requested = pyqtSignal()

    def __init__(
        self,
        remnant_repo: RemnantRepository,
        stock_repo: StockRepository,
        project_repo: ProjectRepository,
        parent=None
    ):
        super().__init__(parent)
        self.remnant_repo = remnant_repo
        self.stock_repo = stock_repo
        self.project_repo = project_repo
        self.remnant_manager = RemnantManager(remnant_repo, stock_repo)
        self.current_result: OptimizationResult = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header with Direct Action Button
        h_box = QHBoxLayout()
        title_box = QVBoxLayout()
        self.h_title = QLabel("📐 نتائج التقطيع والرسوم (Nesting Results)")
        self.h_title.setObjectName("viewTitle")
        self.sub_title = QLabel("مخططات بيانية دقيقة لأعواد الكمرات وألواح الصاج مع تفاصيل التقطيع والفضلات.")
        self.sub_title.setObjectName("viewSubtitle")
        title_box.addWidget(self.h_title)
        title_box.addWidget(self.sub_title)
        h_box.addLayout(title_box)
        h_box.addStretch()

        self.btn_export = QPushButton("📊 تصدير شيت إكسيل للورشة (Export Excel)")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                min-height: 42px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
        """)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_workshop_excel)

        h_box.addWidget(self.btn_export)
        layout.addLayout(h_box)

        # Summary KPIs Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self.kpi_mode = KPICard("Run Mode", "None", "Active algorithm", "#2563EB")
        self.kpi_util = KPICard("Material Utilization", "0.0%", "Overall yield", "#10B981")
        self.kpi_waste = KPICard("Waste Percentage", "0.0%", "Scrap & trimmings", "#EF4444")
        self.kpi_stock = KPICard("Stock Consumed", "0 units", "Bars / plates used", "#8B5CF6")
        self.kpi_remnants = KPICard("Reusable Remnants", "0.0 m", "Usable offcuts saved", "#F59E0B")

        kpi_row.addWidget(self.kpi_mode)
        kpi_row.addWidget(self.kpi_util)
        kpi_row.addWidget(self.kpi_waste)
        kpi_row.addWidget(self.kpi_stock)
        kpi_row.addWidget(self.kpi_remnants)
        layout.addLayout(kpi_row)

        # Main Tabs: Graphical Layouts vs Detailed Cut Table
        self.tabs = QTabWidget()

        # Tab 1: Graphical Visualizer Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.visualizer_container = QWidget()
        self.visualizer_layout = QVBoxLayout(self.visualizer_container)
        self.visualizer_layout.setContentsMargins(10, 10, 10, 10)
        self.visualizer_layout.setSpacing(14)
        self.visualizer_layout.addStretch()
        self.scroll_area.setWidget(self.visualizer_container)
        self.tabs.addTab(self.scroll_area, "📐  مخططات التقطيع المرئية (Cutting Layouts)")

        # Tab 2: Detailed Cut Sequence Table
        self.seq_table = QTableWidget()
        self.seq_table.setColumnCount(8)
        self.seq_table.setHorizontalHeaderLabels([
            "كود العود / اللوح", "القطاع والخامة", "أبعاد الاستوك (mm)", "عدد القطع",
            "توزيعة الأطوال والقطع (mm)", "المستخدم (mm)", "الفضلة (mm)", "نسبة الاستغلال %"
        ])
        self.seq_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.seq_table, "📋  جدول تفاصيل التقطيع وتوزيع الأعواد (Cut Details)")

        # Exceptions Table (Only shown dynamically if there is an actual shortage)
        self.exceptions_table = QTableWidget()
        self.exceptions_table.setColumnCount(4)
        self.exceptions_table.setHorizontalHeaderLabels(["القطعة", "الخامة", "الأبعاد المطلوبة", "سبب عدم التقطيع"])
        self.exceptions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.tabs)

    def display_result(self, result: OptimizationResult):
        self.current_result = result
        self.btn_export.setEnabled(True)

        # Update KPIs
        self.kpi_mode.update_value(result.mode, f"{result.solver_status} ({result.execution_time_sec}s)")
        self.kpi_util.update_value(f"{result.overall_utilization_pct:.1f}%", "Parts / Raw Stock")
        self.kpi_waste.update_value(f"{result.overall_waste_pct:.1f}%", "Unusable scrap")
        self.kpi_stock.update_value(f"{result.total_stock_used} units", f"{result.total_parts_nested} / {result.total_parts_required} parts")
        self.kpi_remnants.update_value(f"{result.total_reusable_remnants_length_m:.1f} m", "Eligible for reuse")

        # Clear existing graphical widgets
        while self.visualizer_layout.count() > 1:
            child = self.visualizer_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Render 1D Linear Bar Visualizers
        if result.linear_plans:
            for plan in result.linear_plans:
                w = BarVisualizerWidget(plan, min_remnant_mm=500.0)
                self.visualizer_layout.insertWidget(self.visualizer_layout.count() - 1, w)

        # Render 2D Plate Visualizers
        elif result.plate_plans:
            for plan in result.plate_plans:
                w = PlateVisualizerWidget(plan)
                self.visualizer_layout.insertWidget(self.visualizer_layout.count() - 1, w)

        # Fill Cut Sequence Table
        self.seq_table.setRowCount(0)
        if result.linear_plans:
            self.seq_table.setRowCount(len(result.linear_plans))
            for row, p in enumerate(result.linear_plans):
                seq_str = " + ".join([f"{s.part_mark} ({s.length:.0f})" for s in p.segments])
                self.seq_table.setItem(row, 0, QTableWidgetItem(f"Bar #{p.bar_index} ({p.stock_id})"))
                self.seq_table.setItem(row, 1, QTableWidgetItem(f"{p.designation} {p.grade}"))
                self.seq_table.setItem(row, 2, QTableWidgetItem(f"{p.stock_length:.0f}"))
                self.seq_table.setItem(row, 3, QTableWidgetItem(str(p.part_count)))
                self.seq_table.setItem(row, 4, QTableWidgetItem(seq_str))
                self.seq_table.setItem(row, 5, QTableWidgetItem(f"{p.used_length:.0f}"))
                self.seq_table.setItem(row, 6, QTableWidgetItem(f"{p.raw_remnant_length:.0f}"))
                
                c_util = QTableWidgetItem(f"{p.utilization_pct:.1f}%")
                if p.utilization_pct >= 90.0:
                    c_util.setForeground(Qt.GlobalColor.green)
                self.seq_table.setItem(row, 7, c_util)

        elif result.plate_plans:
            self.seq_table.setRowCount(len(result.plate_plans))
            for row, pl in enumerate(result.plate_plans):
                seq_str = ", ".join([f"{p.part_mark} ({p.width:.0f}x{p.length:.0f})" for p in pl.parts])
                self.seq_table.setItem(row, 0, QTableWidgetItem(f"Plate #{pl.plate_index} ({pl.stock_id})"))
                self.seq_table.setItem(row, 1, QTableWidgetItem(f"PL {pl.thickness_mm}mm {pl.grade}"))
                self.seq_table.setItem(row, 2, QTableWidgetItem(f"{pl.plate_width:.0f} x {pl.plate_length:.0f}"))
                self.seq_table.setItem(row, 3, QTableWidgetItem(str(pl.part_count)))
                self.seq_table.setItem(row, 4, QTableWidgetItem(seq_str))
                self.seq_table.setItem(row, 5, QTableWidgetItem(f"{pl.used_parts_area_m2:.2f} m²"))
                self.seq_table.setItem(row, 6, QTableWidgetItem(f"{pl.total_plate_area_m2 - pl.used_parts_area_m2:.2f} m²"))
                self.seq_table.setItem(row, 7, QTableWidgetItem(f"{pl.utilization_pct:.1f}%"))

        # Fill Exceptions & Shortages Table (Shown ONLY if there are unassigned parts or shortages)
        all_exceptions = []
        for p in result.unassigned_parts:
            all_exceptions.append((p.part_mark, f"{p.designation} {p.grade}", str(p.length_or_dims), p.reason))
        for short_item, short_qty in result.shortages.items():
            all_exceptions.append(("عجز في المخزن", short_item, f"مطلوب {short_qty} وحدة إضافية", "نفدت كميات الاستوك المتاحة بالمخزن؛ يلزم توريد أطوال جديدة."))

        if all_exceptions:
            if self.tabs.indexOf(self.exceptions_table) == -1:
                self.tabs.addTab(self.exceptions_table, "⚠️  قطع لم يتم استيعابها (Shortages)")
            self.exceptions_table.setRowCount(len(all_exceptions))
            for row, (item, mat, dims, note) in enumerate(all_exceptions):
                self.exceptions_table.setItem(row, 0, QTableWidgetItem(item))
                self.exceptions_table.setItem(row, 1, QTableWidgetItem(mat))
                self.exceptions_table.setItem(row, 2, QTableWidgetItem(dims))
                c_note = QTableWidgetItem(note)
                c_note.setForeground(Qt.GlobalColor.red)
                self.exceptions_table.setItem(row, 3, c_note)
        else:
            # If no shortages, ensure the tab is hidden and not cluttering the screen
            idx = self.tabs.indexOf(self.exceptions_table)
            if idx != -1:
                self.tabs.removeTab(idx)

    def _export_workshop_excel(self):
        if not self.current_result:
            QMessageBox.warning(self, "لا توجد نتائج", "يرجى تشغيل عملية التقطيع أولاً قبل التصدير.")
            return

        proj = self.project_repo.get(self.current_result.project_id) if self.project_repo and self.current_result.project_id else None
        if not proj:
            from steel_nest.models.project import Project, ProjectSettings
            proj = Project(id="QUICK-PRJ", name="مشروع تقطيع الورشة", code="PRJ-01")

        default_name = f"SteelNest_Cutting_Plan_{self.current_result.project_id or 'Workshop'}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "حفظ وتصدير شيت إكسيل للورشة", default_name, "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            ExcelReportExporter.export_workshop_workbook(file_path, proj, self.current_result)
            import os
            try:
                os.startfile(file_path)
            except Exception:
                pass
            QMessageBox.information(
                self,
                "تم التصدير بنجاح",
                f"تم إنشاء وتصدير شيت الإكسيل بنجاح وفتحه في Microsoft Excel:\n{file_path}"
            )
        except Exception as ex:
            QMessageBox.critical(self, "خطأ في التصدير", f"تعذر حفظ وتصدير ملف الإكسيل:\n{str(ex)}")
