"""
Professional Statistics Dashboard for SteelNest Pro
Faithfully replicates the complete statistics structure and tabbed categories
of Cutting Optimization Pro:
- Top Sub-Tabs: Statistics (2D) | Statistics (1D) | Price
- Inner Categories:
  1. Utilized parts
  2. Utilized sheets / Utilized bars
  3. Cuts
  4. Reused waste
  5. Disposed waste
  6. Materials
  7. Summary
  8. Other statistics
"""
from typing import Optional, List, Dict, Any
from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QDialog, QPushButton, QFileDialog, QMessageBox, QScrollArea,
    QGridLayout, QApplication, QSplitter, QAbstractItemView
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPageSize, QPageLayout, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from steel_nest.models.nesting_plan import OptimizationResult, PlateNestPlan, LinearBarPlan


TABLE_STYLE_CUTTING_PRO = """
    QTableWidget {
        background-color: #FFFFFF;
        alternate-background-color: #F8FAFC;
        gridline-color: #A0B0C8;
        font-size: 11px;
        color: #000000;
    }
    QHeaderView::section {
        background-color: #C6D9F1;
        color: #000000;
        font-weight: bold;
        border: 1px solid #94A8C6;
        padding: 4px 6px;
    }
    QTableWidget::item:selected {
        background-color: #B8D0EC;
        color: #000000;
    }
"""

class StatSectionPanel(QWidget):
    """Panel containing the 8 sub-category tabs for 1D or 2D statistics."""
    def __init__(self, mode: str = "1D", parent=None):
        super().__init__(parent)
        self.mode = mode  # "1D" or "2D"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet("""
            QTabBar::tab {
                background: #EAEFF5;
                color: #1E293B;
                padding: 5px 12px;
                border: 1px solid #CBD5E1;
                font-weight: bold;
                font-size: 11px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #1D4ED8;
                border-bottom: 2px solid #2563EB;
            }
        """)

        # 1. Utilized parts
        self.table_parts = QTableWidget()
        headers_parts = ["#", "Length ▲", "Width", "Quantity", "Material", "Texture", "Label", "Customer name"] if self.mode == "2D" else ["#", "Length ▲", "Quantity", "Material", "Label", "Customer name"]
        self._setup_table(self.table_parts, headers_parts)
        self.sub_tabs.addTab(self.table_parts, "Utilized parts")

        # 2. Utilized sheets / Utilized bars
        self.table_stock = QTableWidget()
        sheet_label = "Utilized sheets" if self.mode == "2D" else "Utilized bars"
        headers_stock = ["#", "Length", "Width", "Quantity", "Material", "Label", "Price"] if self.mode == "2D" else ["#", "Length", "Quantity", "Material", "Label", "Price"]
        self._setup_table(self.table_stock, headers_stock)
        self.sub_tabs.addTab(self.table_stock, sheet_label)

        # 3. Cuts
        self.table_cuts = QTableWidget()
        headers_cuts = ["#", "Sheet #", "Cut #", "Stage", "Direction", "Start (X, Y)", "End (X, Y)", "Length (mm)", "Part Mark"] if self.mode == "2D" else ["#", "Bar #", "Cut #", "Part Mark", "Length", "Start Pos", "End Pos", "Saw Kerf"]
        self._setup_table(self.table_cuts, headers_cuts)
        self.sub_tabs.addTab(self.table_cuts, "Cuts")

        # 4. Reused waste
        self.table_reused = QTableWidget()
        headers_reused = ["#", "Length", "Width", "Material", "Quantity"] if self.mode == "2D" else ["#", "Length", "Material", "Quantity"]
        self._setup_table(self.table_reused, headers_reused)
        self.sub_tabs.addTab(self.table_reused, "Reused waste")

        # 5. Disposed waste
        self.table_disposed = QTableWidget()
        headers_disposed = ["#", "Length", "Width", "Material", "Quantity"] if self.mode == "2D" else ["#", "Length", "Material", "Quantity"]
        self._setup_table(self.table_disposed, headers_disposed)
        self.sub_tabs.addTab(self.table_disposed, "Disposed waste")

        # 6. Materials
        self.table_materials = QTableWidget()
        headers_mat = [
            "#", "Material", "Total used length", "Total used length %",
            "Reused waste", "Disposed waste", "Size of used bars",
            "Price (PIECES)", "Price (Stock)", "Number of utilized parts"
        ] if self.mode == "1D" else [
            "#", "Material", "Total used area (m²)", "Total used area %",
            "Reused waste (m²)", "Disposed waste (m²)", "Size of used sheets",
            "Price (PIECES)", "Price (Stock)", "Number of utilized parts"
        ]
        self._setup_table(self.table_materials, headers_mat)
        self.sub_tabs.addTab(self.table_materials, "Materials")

        # 7. Summary
        self.panel_summary = QWidget()
        self._setup_summary_panel(self.panel_summary)
        self.sub_tabs.addTab(self.panel_summary, "Summary")

        # 8. Other statistics
        self.table_other = QTableWidget()
        self._setup_table(self.table_other, ["Parameter", "Value"])
        self.table_other.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_other.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.sub_tabs.addTab(self.table_other, "Other statistics")

        layout.addWidget(self.sub_tabs)

    def _setup_table(self, table: QTableWidget, headers: List[str]):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(TABLE_STYLE_CUTTING_PRO)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def _setup_summary_panel(self, panel: QWidget):
        p_layout = QVBoxLayout(panel)
        p_layout.setContentsMargins(6, 6, 6, 6)
        p_layout.setSpacing(6)

        # Summary Tab matching Cutting Optimization Pro Image media_1792951567795_9eb646e9.png
        self.table_summary_grid = QTableWidget()
        headers_summary = ["#", "Length ▲", "Width", "Quantity", "Material", "Label", "PIECES", "Waste"] if self.mode == "2D" else ["#", "Length ▲", "Quantity", "Material", "Label", "PIECES", "Waste"]
        self._setup_table(self.table_summary_grid, headers_summary)
        self.table_summary_grid.setWordWrap(True)
        self.table_summary_grid.verticalHeader().setVisible(False)
        self.table_summary_grid.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_summary_grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        if self.mode == "2D":
            self.table_summary_grid.setColumnWidth(0, 45)
            self.table_summary_grid.setColumnWidth(1, 85)
            self.table_summary_grid.setColumnWidth(2, 85)
            self.table_summary_grid.setColumnWidth(3, 75)
            self.table_summary_grid.setColumnWidth(4, 90)
            self.table_summary_grid.setColumnWidth(5, 90)
            self.table_summary_grid.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
            self.table_summary_grid.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        else:
            self.table_summary_grid.setColumnWidth(0, 45)
            self.table_summary_grid.setColumnWidth(1, 95)
            self.table_summary_grid.setColumnWidth(2, 75)
            self.table_summary_grid.setColumnWidth(3, 100)
            self.table_summary_grid.setColumnWidth(4, 100)
            self.table_summary_grid.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
            self.table_summary_grid.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        p_layout.addWidget(self.table_summary_grid)

    def _set_cell(self, table: QTableWidget, r: int, c: int, val: str, align=Qt.AlignmentFlag.AlignLeft):
        item = QTableWidgetItem(str(val))
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setToolTip(str(val))
        if c == 0:
            item.setBackground(QColor("#DCE6F1"))
            item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        table.setItem(r, c, item)


class PriceStatisticsPanel(QWidget):
    """Financial Summary Tab: Costs, Materials Pricing, Scrap Savings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl = QLabel("Price & Economic Material Evaluation — التكلفة والميزانية")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #1E3A8A;")
        layout.addWidget(lbl)

        self.table_price = QTableWidget()
        headers = ["Cost Category", "Gross Amount", "Percentage %", "Notes"]
        self.table_price.setColumnCount(len(headers))
        self.table_price.setHorizontalHeaderLabels(headers)
        self.table_price.setAlternatingRowColors(True)
        self.table_price.verticalHeader().setVisible(False)
        self.table_price.setStyleSheet(TABLE_STYLE_CUTTING_PRO)
        self.table_price.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_price.horizontalHeader().setStretchLastSection(True)
        self.table_price.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_price.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_price)

    def update_data(self, result: Optional[OptimizationResult]):
        if not result:
            self.table_price.setRowCount(0)
            return

        self.table_price.setRowCount(0)
        cost_total = result.total_estimated_cost
        u = result.overall_utilization_pct
        w = result.overall_waste_pct

        val_used = cost_total * (u / 100.0)
        val_scrap = cost_total * (w / 100.0)

        rows = [
            ("Raw Stock Purchased Cost", f"${cost_total:,.2f}", "100.0 %", "Total raw material allocated"),
            ("Net Finished Parts Value", f"${val_used:,.2f}", f"{u:.2f} %", "Value materialized in required cuts"),
            ("Waste / Scrap Material Cost", f"${val_scrap:,.2f}", f"{w:.2f} %", "Scrap loss from drops & offcuts"),
            ("Reusable Offcuts Value (Salvaged)", f"${val_scrap * 0.7:,.2f}", f"{w * 0.7:.2f} %", "Saved material committed back to stock repository"),
            ("Net Manufacturing Cost", f"${cost_total - (val_scrap * 0.7):,.2f}", "-", "Raw stock minus recovered remnants"),
        ]

        self.table_price.setRowCount(len(rows))
        for r, (cat, val, pct, note) in enumerate(rows):
            it0 = QTableWidgetItem(cat)
            it0.setBackground(QColor("#DCE6F1"))
            it0.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table_price.setItem(r, 0, it0)
            self.table_price.setItem(r, 1, QTableWidgetItem(val))
            self.table_price.setItem(r, 2, QTableWidgetItem(pct))
            self.table_price.setItem(r, 3, QTableWidgetItem(note))


class StatisticsDashboard(QWidget):
    """
    Complete Statistics Tab View replicating Cutting Optimization Pro's exact layout:
    - Top Tabs: Statistics (2D) | Statistics (1D) | Price
    - Sub-categories: Utilized parts, Utilized sheets/bars, Cuts, Reused waste,
      Disposed waste, Materials, Summary, Other statistics.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Top Level Tabs matching Image 2: Statistics (2D) | Statistics (1D) | Price
        self.top_tabs = QTabWidget()
        self.top_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 18px;
                font-weight: bold;
                font-size: 12px;
            }
        """)

        # 1. Statistics (2D)
        self.panel_2d = StatSectionPanel(mode="2D")
        self.top_tabs.addTab(self.panel_2d, "Statistics (2D)")

        # 2. Statistics (1D)
        self.panel_1d = StatSectionPanel(mode="1D")
        self.top_tabs.addTab(self.panel_1d, "Statistics (1D)")

        # 3. Price
        self.panel_price = PriceStatisticsPanel()
        self.top_tabs.addTab(self.panel_price, "Price")

        main_layout.addWidget(self.top_tabs)

    def update_statistics(self, result: Optional[OptimizationResult]):
        if not result:
            self._clear_all()
            return

        self._populate_1d(result)
        self._populate_2d(result)
        self.panel_price.update_data(result)

        # Automatically select the relevant top tab
        if result.plate_plans and not result.linear_plans:
            self.top_tabs.setCurrentIndex(0)  # 2D
        elif result.linear_plans and not result.plate_plans:
            self.top_tabs.setCurrentIndex(1)  # 1D
        else:
            self.top_tabs.setCurrentIndex(0 if result.plate_plans else 1)

    def _populate_1d(self, result: OptimizationResult):
        p = self.panel_1d
        plans = result.linear_plans
        if not plans:
            self._clear_panel(p)
            return

        # 1. Utilized parts
        # Aggregate parts by (length, material, mark)
        parts_agg = defaultdict(int)
        for plan in plans:
            reps = plan.repetition_count
            for seg in plan.segments:
                key = (seg.length, plan.designation, seg.part_mark)
                parts_agg[key] += reps

        p.table_parts.setRowCount(len(parts_agg))
        for r, ((length, mat, mark), qty) in enumerate(parts_agg.items()):
            p._set_cell(p.table_parts, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_parts, r, 1, f"{length:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_parts, r, 2, f"{qty}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_parts, r, 3, mat)
            p._set_cell(p.table_parts, r, 4, mark)
            p._set_cell(p.table_parts, r, 5, "")  # Customer name

        # 2. Utilized bars
        # Aggregate bars by (stock_length, designation, stock_id, unit_cost)
        bars_agg = defaultdict(int)
        for plan in plans:
            key = (plan.stock_length, plan.designation, plan.stock_id, plan.unit_cost)
            bars_agg[key] += plan.repetition_count

        p.table_stock.setRowCount(len(bars_agg))
        for r, ((length, mat, lbl, price), qty) in enumerate(bars_agg.items()):
            p._set_cell(p.table_stock, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_stock, r, 1, f"{length:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_stock, r, 2, f"{qty}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_stock, r, 3, mat)
            p._set_cell(p.table_stock, r, 4, lbl)
            p._set_cell(p.table_stock, r, 5, f"{price:.2f}" if price > 0 else "0")

        # 3. Cuts sequence
        cut_rows = []
        for plan in plans:
            for c_idx, seg in enumerate(plan.segments):
                cut_rows.append((
                    f"#{plan.bar_index} (x{plan.repetition_count})",
                    f"{c_idx + 1}",
                    seg.part_mark,
                    f"{seg.length:.0f}",
                    f"{seg.start_pos:.0f}",
                    f"{seg.end_pos:.0f}",
                    f"{seg.kerf_after:.1f}"
                ))

        p.table_cuts.setRowCount(len(cut_rows))
        for r, row in enumerate(cut_rows):
            p._set_cell(p.table_cuts, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            for c, val in enumerate(row):
                p._set_cell(p.table_cuts, r, c + 1, val)

        # 4. Reused waste & 5. Disposed waste
        reused_agg = defaultdict(int)
        disposed_agg = defaultdict(int)
        for plan in plans:
            rem = plan.raw_remnant_length
            reps = plan.repetition_count
            if rem >= 500.0:  # Useful waste threshold
                reused_agg[(rem, plan.designation)] += reps
            elif rem > 0:
                disposed_agg[(rem, plan.designation)] += reps

        p.table_reused.setRowCount(len(reused_agg))
        for r, ((rem_len, mat), qty) in enumerate(reused_agg.items()):
            p._set_cell(p.table_reused, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_reused, r, 1, f"{rem_len:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_reused, r, 2, mat)
            p._set_cell(p.table_reused, r, 3, f"{qty}", Qt.AlignmentFlag.AlignRight)

        p.table_disposed.setRowCount(len(disposed_agg))
        for r, ((rem_len, mat), qty) in enumerate(disposed_agg.items()):
            p._set_cell(p.table_disposed, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_disposed, r, 1, f"{rem_len:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_disposed, r, 2, mat)
            p._set_cell(p.table_disposed, r, 3, f"{qty}", Qt.AlignmentFlag.AlignRight)

        # 6. Materials
        # Aggregate by material
        mat_stats = defaultdict(lambda: {
            "used_len": 0.0, "total_len": 0.0, "reused": 0.0, "disposed": 0.0,
            "parts_cnt": 0, "price_pieces": 0.0, "price_stock": 0.0
        })

        for plan in plans:
            reps = plan.repetition_count
            m = plan.designation
            stk_len = plan.stock_length * reps
            part_len = plan.total_part_length * reps
            rem_len = plan.raw_remnant_length * reps
            cost = plan.unit_cost * reps

            mat_stats[m]["total_len"] += stk_len
            mat_stats[m]["used_len"] += part_len
            mat_stats[m]["parts_cnt"] += len(plan.segments) * reps
            mat_stats[m]["price_stock"] += cost

            if plan.raw_remnant_length >= 500.0:
                mat_stats[m]["reused"] += rem_len
            else:
                mat_stats[m]["disposed"] += rem_len

        p.table_materials.setRowCount(len(mat_stats))
        for r, (mat, data) in enumerate(mat_stats.items()):
            tot = data["total_len"]
            usd = data["used_len"]
            pct = (usd / tot * 100.0) if tot > 0 else 0.0
            p._set_cell(p.table_materials, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_materials, r, 1, mat)
            p._set_cell(p.table_materials, r, 2, f"{usd:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 3, f"{pct:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 4, f"{data['reused']:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 5, f"{data['disposed']:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 6, f"{tot:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 7, f"{data['price_pieces']:.2f}")
            p._set_cell(p.table_materials, r, 8, f"{data['price_stock']:.2f}")
            p._set_cell(p.table_materials, r, 9, f"{data['parts_cnt']}", Qt.AlignmentFlag.AlignRight)

        tot_used_len = sum(d["used_len"] for d in mat_stats.values())
        tot_stk_len = sum(d["total_len"] for d in mat_stats.values())
        tot_reused = sum(d["reused"] for d in mat_stats.values())
        tot_disposed = sum(d["disposed"] for d in mat_stats.values())
        tot_parts = sum(d["parts_cnt"] for d in mat_stats.values())

        # 7. Summary Grid (1D) matching Image media_1792951567795_9eb646e9.png
        p.table_summary_grid.setRowCount(len(plans))
        for r, plan in enumerate(plans):
            p._set_cell(p.table_summary_grid, r, 0, f"{plan.bar_index}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 1, f"{plan.stock_length:.0f}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 2, f"{plan.repetition_count}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 3, plan.designation, Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 4, plan.stock_id or plan.grade or "Bar", Qt.AlignmentFlag.AlignCenter)

            pieces_dict = defaultdict(int)
            for seg in plan.segments:
                pieces_dict[f"{seg.length:.0f}"] += 1
            pieces_lines = [f"{cnt}x - {k}" for k, cnt in sorted(pieces_dict.items(), key=lambda x: -x[1])]
            p._set_cell(p.table_summary_grid, r, 5, "\n".join(pieces_lines), Qt.AlignmentFlag.AlignLeft)

            rem = plan.raw_remnant_length
            waste_str = f"1x - {rem:.0f}" if rem > 0 else "0 mm"
            p._set_cell(p.table_summary_grid, r, 6, waste_str, Qt.AlignmentFlag.AlignLeft)

        # 8. Other statistics table matching Image 2 & CSV
        reused_pct = (tot_reused / tot_stk_len * 100.0) if tot_stk_len > 0 else 0.0
        disposed_pct = (tot_disposed / tot_stk_len * 100.0) if tot_stk_len > 0 else 0.0

        other_rows = [
            ("Total used length", f"{tot_used_len:.0f}"),
            ("Number of pieces", f"{tot_parts}"),
            ("Size of used bars", f"{tot_stk_len:.0f}"),
            ("Reused waste", f"{tot_reused:.0f}"),
            ("Reused waste %", f"{reused_pct:.1f}"),
            ("Disposed waste", f"{tot_disposed:.0f}"),
            ("Disposed waste %", f"{disposed_pct:.1f}"),
            ("Utilized parts (Price)", "0"),
            ("Bars (Price)", f"{sum(d['price_stock'] for d in mat_stats.values()):.2f}"),
            ("Running time", f"{result.execution_time_sec:.3f}s"),
        ]
        p.table_other.setRowCount(len(other_rows))
        for r, (param, val) in enumerate(other_rows):
            it0 = QTableWidgetItem(param)
            it0.setBackground(QColor("#DCE6F1"))
            it0.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.table_other.setItem(r, 0, it0)
            p.table_other.setItem(r, 1, QTableWidgetItem(val))

    def _populate_2d(self, result: OptimizationResult):
        p = self.panel_2d
        plans = result.plate_plans
        if not plans:
            self._clear_panel(p)
            return

        # 1. Utilized parts (2D)
        parts_agg = defaultdict(int)
        for plan in plans:
            reps = plan.repetition_count
            for part in plan.parts:
                key = (part.length, part.width, plan.grade, part.part_mark)
                parts_agg[key] += reps

        p.table_parts.setRowCount(len(parts_agg))
        for r, ((length, width, mat, mark), qty) in enumerate(parts_agg.items()):
            p._set_cell(p.table_parts, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_parts, r, 1, f"{length:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_parts, r, 2, f"{width:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_parts, r, 3, f"{qty}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_parts, r, 4, mat)
            p._set_cell(p.table_parts, r, 5, "")  # Texture
            p._set_cell(p.table_parts, r, 6, mark)
            p._set_cell(p.table_parts, r, 7, "")  # Customer name

        # 2. Utilized sheets
        sheets_agg = defaultdict(int)
        for plan in plans:
            key = (plan.plate_length, plan.plate_width, plan.grade, plan.stock_id, plan.unit_cost)
            sheets_agg[key] += plan.repetition_count

        p.table_stock.setRowCount(len(sheets_agg))
        for r, ((length, width, mat, lbl, price), qty) in enumerate(sheets_agg.items()):
            p._set_cell(p.table_stock, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_stock, r, 1, f"{length:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_stock, r, 2, f"{width:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_stock, r, 3, f"{qty}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_stock, r, 4, mat)
            p._set_cell(p.table_stock, r, 5, lbl)
            p._set_cell(p.table_stock, r, 6, f"{price:.2f}" if price > 0 else "0")

        # 3. Cuts sequence (2D)
        cut_rows = []
        for plan in plans:
            for c_idx, c in enumerate(plan.cut_lines):
                cut_rows.append((
                    f"#{plan.plate_index} (x{plan.repetition_count})",
                    f"{c_idx + 1}",
                    f"{c.get('stage', 1)}",
                    c.get('type', 'CUT'),
                    f"({c.get('x1', 0):.0f}, {c.get('y1', 0):.0f})",
                    f"({c.get('x2', 0):.0f}, {c.get('y2', 0):.0f})",
                    f"{c.get('length', 0):.1f}",
                    c.get('mark', '')
                ))

        p.table_cuts.setRowCount(len(cut_rows))
        for r, row in enumerate(cut_rows):
            p._set_cell(p.table_cuts, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            for c, val in enumerate(row):
                p._set_cell(p.table_cuts, r, c + 1, val)

        # 4. Reused waste & 5. Disposed waste
        reused_agg = defaultdict(int)
        disposed_agg = defaultdict(int)
        for plan in plans:
            reps = plan.repetition_count
            tot_a = plan.total_plate_area_m2
            usd_a = plan.used_parts_area_m2
            waste_a = max(0.0, tot_a - usd_a)
            if waste_a >= 0.5:
                reused_agg[(plan.plate_length, plan.plate_width, plan.grade)] += reps
            elif waste_a > 0:
                disposed_agg[(plan.plate_length, plan.plate_width, plan.grade)] += reps

        p.table_reused.setRowCount(len(reused_agg))
        for r, ((l, w, mat), qty) in enumerate(reused_agg.items()):
            p._set_cell(p.table_reused, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_reused, r, 1, f"{l:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_reused, r, 2, f"{w:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_reused, r, 3, mat)
            p._set_cell(p.table_reused, r, 4, f"{qty}", Qt.AlignmentFlag.AlignRight)

        p.table_disposed.setRowCount(len(disposed_agg))
        for r, ((l, w, mat), qty) in enumerate(disposed_agg.items()):
            p._set_cell(p.table_disposed, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_disposed, r, 1, f"{l:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_disposed, r, 2, f"{w:.0f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_disposed, r, 3, mat)
            p._set_cell(p.table_disposed, r, 4, f"{qty}", Qt.AlignmentFlag.AlignRight)

        # 6. Materials (2D)
        mat_stats = defaultdict(lambda: {
            "used_area": 0.0, "total_area": 0.0, "reused": 0.0, "disposed": 0.0,
            "parts_cnt": 0, "price_pieces": 0.0, "price_stock": 0.0
        })

        for plan in plans:
            reps = plan.repetition_count
            m = plan.grade
            stk_a = plan.total_plate_area_m2 * reps
            part_a = plan.used_parts_area_m2 * reps
            rem_a = max(0.0, stk_a - part_a)
            cost = plan.unit_cost * reps

            mat_stats[m]["total_area"] += stk_a
            mat_stats[m]["used_area"] += part_a
            mat_stats[m]["parts_cnt"] += len(plan.parts) * reps
            mat_stats[m]["price_stock"] += cost

            if (stk_a - part_a) / reps >= 0.5:
                mat_stats[m]["reused"] += rem_a
            else:
                mat_stats[m]["disposed"] += rem_a

        p.table_materials.setRowCount(len(mat_stats))
        for r, (mat, data) in enumerate(mat_stats.items()):
            tot = data["total_area"]
            usd = data["used_area"]
            pct = (usd / tot * 100.0) if tot > 0 else 0.0
            p._set_cell(p.table_materials, r, 0, f"{r + 1}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_materials, r, 1, mat)
            p._set_cell(p.table_materials, r, 2, f"{usd:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 3, f"{pct:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 4, f"{data['reused']:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 5, f"{data['disposed']:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 6, f"{tot:.3f}", Qt.AlignmentFlag.AlignRight)
            p._set_cell(p.table_materials, r, 7, f"{data['price_pieces']:.2f}")
            p._set_cell(p.table_materials, r, 8, f"{data['price_stock']:.2f}")
            p._set_cell(p.table_materials, r, 9, f"{data['parts_cnt']}", Qt.AlignmentFlag.AlignRight)

        tot_used_a = sum(d["used_area"] for d in mat_stats.values())
        tot_stk_a = sum(d["total_area"] for d in mat_stats.values())
        tot_reused_a = sum(d["reused"] for d in mat_stats.values())
        tot_disposed_a = sum(d["disposed"] for d in mat_stats.values())
        tot_parts_2d = sum(d["parts_cnt"] for d in mat_stats.values())

        # 7. Summary Grid (2D) matching Image media_1792951567795_9eb646e9.png
        p.table_summary_grid.setRowCount(len(plans))
        for r, plan in enumerate(plans):
            p._set_cell(p.table_summary_grid, r, 0, f"{plan.plate_index}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 1, f"{plan.plate_length:.0f}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 2, f"{plan.plate_width:.0f}", Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 3, f"{plan.repetition_count}", Qt.AlignmentFlag.AlignCenter)
            
            desig = f"PL {int(plan.thickness_mm) if plan.thickness_mm.is_integer() else plan.thickness_mm}" if plan.thickness_mm > 0 else (plan.grade or "PL")
            p._set_cell(p.table_summary_grid, r, 4, desig, Qt.AlignmentFlag.AlignCenter)
            p._set_cell(p.table_summary_grid, r, 5, plan.stock_id or plan.grade or "Sheet", Qt.AlignmentFlag.AlignCenter)

            pieces_dict = defaultdict(int)
            for pt in plan.parts:
                key = f"{pt.length:.0f}x{pt.width:.0f}"
                pieces_dict[key] += 1
            pieces_lines = [f"{cnt}x - {k}" for k, cnt in sorted(pieces_dict.items(), key=lambda x: -x[1])]
            p._set_cell(p.table_summary_grid, r, 6, "\n".join(pieces_lines), Qt.AlignmentFlag.AlignLeft)

            waste_lines = []
            if hasattr(plan, "waste_rects") and plan.waste_rects:
                w_dict = defaultdict(int)
                for wr in plan.waste_rects:
                    wl = wr.get("length", 0)
                    ww = wr.get("width", 0)
                    if wl > 5 and ww > 5:
                        key = f"{wl:.0f}x{ww:.0f}"
                        w_dict[key] += 1
                waste_lines = [f"{cnt}x - {k}" for k, cnt in sorted(w_dict.items(), key=lambda x: -x[1])]

            if not waste_lines:
                waste_a = getattr(plan, "waste_area", 0.0)
                if waste_a > 0:
                    waste_lines = [f"Waste: {waste_a/1_000_000.0:.2f} m² ({plan.waste_pct:.1f}%)"]
                else:
                    waste_lines = ["0 mm (0.0%)"]
            p._set_cell(p.table_summary_grid, r, 7, "\n".join(waste_lines), Qt.AlignmentFlag.AlignLeft)

        # 8. Other statistics (2D)
        reused_pct = (tot_reused_a / tot_stk_a * 100.0) if tot_stk_a > 0 else 0.0
        disposed_pct = (tot_disposed_a / tot_stk_a * 100.0) if tot_stk_a > 0 else 0.0

        other_rows_2d = [
            ("Total used area (m²)", f"{tot_used_a:.3f}"),
            ("Number of pieces", f"{tot_parts_2d}"),
            ("Size of used sheets (m²)", f"{tot_stk_a:.3f}"),
            ("Reused waste (m²)", f"{tot_reused_a:.3f}"),
            ("Reused waste %", f"{reused_pct:.1f}"),
            ("Disposed waste (m²)", f"{tot_disposed_a:.3f}"),
            ("Disposed waste %", f"{disposed_pct:.1f}"),
            ("Utilized parts (Price)", "0"),
            ("Sheets (Price)", f"{sum(d['price_stock'] for d in mat_stats.values()):.2f}"),
            ("Running time", f"{result.execution_time_sec:.3f}s"),
        ]
        p.table_other.setRowCount(len(other_rows_2d))
        for r, (param, val) in enumerate(other_rows_2d):
            it0 = QTableWidgetItem(param)
            it0.setBackground(QColor("#DCE6F1"))
            it0.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.table_other.setItem(r, 0, it0)
            p.table_other.setItem(r, 1, QTableWidgetItem(val))

    def _clear_panel(self, p: StatSectionPanel):
        p.table_parts.setRowCount(0)
        p.table_stock.setRowCount(0)
        p.table_cuts.setRowCount(0)
        p.table_reused.setRowCount(0)
        p.table_disposed.setRowCount(0)
        p.table_materials.setRowCount(0)
        p.table_summary_grid.setRowCount(0)
        p.table_other.setRowCount(0)

    def _clear_all(self):
        self._clear_panel(self.panel_1d)
        self._clear_panel(self.panel_2d)
        self.panel_price.table_price.setRowCount(0)


class TabularCutDialog(QDialog):
    """
    Saw Operator's Tabular Cutting Sequence Table.
    Allows workshop staff to follow exact cutting steps and coordinates.
    """
    def __init__(self, result: OptimizationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("📋 Tabular Cutting Coordinates & Sequence")
        self.resize(850, 550)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        lbl_desc = QLabel("Detailed cutting instructions and coordinates for shop fabrication:")
        lbl_desc.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lbl_desc)

        self.table = QTableWidget()
        headers = [
            "Pattern", "Cut #", "Part Mark", "Material",
            "Length (mm)", "Width (mm)", "Pos X (mm)", "Pos Y (mm)",
            "Rotated", "Stock ID"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(TABLE_STYLE_CUTTING_PRO)

        r = 0
        for b_idx, bar in enumerate(self.result.linear_plans):
            for c_idx, c in enumerate(bar.segments):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(f"Bar #{b_idx + 1} (x{bar.repetition_count})"))
                self.table.setItem(r, 1, QTableWidgetItem(f"{c_idx + 1}"))
                self.table.setItem(r, 2, QTableWidgetItem(c.part_mark))
                self.table.setItem(r, 3, QTableWidgetItem(bar.designation))
                self.table.setItem(r, 4, QTableWidgetItem(f"{c.length:.0f}"))
                self.table.setItem(r, 5, QTableWidgetItem("-"))
                self.table.setItem(r, 6, QTableWidgetItem(f"{c.start_pos:.0f}"))
                self.table.setItem(r, 7, QTableWidgetItem("0"))
                self.table.setItem(r, 8, QTableWidgetItem("No"))
                self.table.setItem(r, 9, QTableWidgetItem(bar.stock_id))
                r += 1

        for pl_idx, pl in enumerate(self.result.plate_plans):
            for c_idx, part in enumerate(pl.parts):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(f"Plate #{pl_idx + 1} (x{pl.repetition_count})"))
                self.table.setItem(r, 1, QTableWidgetItem(f"{c_idx + 1}"))
                self.table.setItem(r, 2, QTableWidgetItem(part.part_mark))
                self.table.setItem(r, 3, QTableWidgetItem(f"PL {pl.thickness_mm:.0f}mm {pl.grade}"))
                self.table.setItem(r, 4, QTableWidgetItem(f"{part.length:.0f}"))
                self.table.setItem(r, 5, QTableWidgetItem(f"{part.width:.0f}"))
                self.table.setItem(r, 6, QTableWidgetItem(f"{part.x:.0f}"))
                self.table.setItem(r, 7, QTableWidgetItem(f"{part.y:.0f}"))
                self.table.setItem(r, 8, QTableWidgetItem("Yes (90°)" if part.rotated else "No"))
                self.table.setItem(r, 9, QTableWidgetItem(pl.stock_id))
                r += 1

        layout.addWidget(self.table)


class StickersDialog(QDialog):
    """
    Workshop Adhesive Labels / Stickers Printing Dialog.
    Allows printing stickers for each cut piece with Barcode/QR, Part Mark, Dimensions, and Material.
    """
    def __init__(self, result: OptimizationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("🏷️ Workshop Stickers & Adhesive Labels")
        self.resize(750, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        lbl_info = QLabel("Preview of Part Identification Stickers for shop floor labeling:")
        lbl_info.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        top_row.addWidget(lbl_info)
        top_row.addStretch()

        btn_print = QPushButton("🖨️ Print Stickers")
        btn_print.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_print.clicked.connect(self._print_stickers)
        top_row.addWidget(btn_print)
        layout.addLayout(top_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.grid = QGridLayout(self.scroll_widget)
        self.grid.setSpacing(10)

        # Generate sticker widgets
        col = 0
        row = 0
        idx = 0

        # Linear parts stickers
        for bar in self.result.linear_plans:
            for seg in bar.segments:
                for _ in range(bar.repetition_count):
                    stk = self._create_sticker(
                        seg.part_mark, bar.designation, f"{seg.length:.0f} mm",
                        f"Bar #{bar.bar_index}", bar.stock_id
                    )
                    self.grid.addWidget(stk, row, col)
                    col += 1
                    if col >= 3:
                        col = 0
                        row += 1
                    idx += 1

        # Plate parts stickers
        for pl in self.result.plate_plans:
            for part in pl.parts:
                for _ in range(pl.repetition_count):
                    stk = self._create_sticker(
                        part.part_mark, f"PL {pl.thickness_mm:.0f}mm {pl.grade}",
                        f"{part.length:.0f} × {part.width:.0f} mm",
                        f"Sheet #{pl.plate_index}", pl.stock_id
                    )
                    self.grid.addWidget(stk, row, col)
                    col += 1
                    if col >= 3:
                        col = 0
                        row += 1
                    idx += 1

        self.scroll.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll)

    def _create_sticker(self, mark: str, mat: str, dims: str, parent_src: str, stk_id: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 2px dashed #94A3B8;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        l = QVBoxLayout(f)
        l.setSpacing(2)

        lbl_m = QLabel(f"<b>MARK:</b> <font color='#1E40AF' size='+1'>{mark}</font>")
        lbl_d = QLabel(f"<b>Size:</b> {dims}")
        lbl_mat = QLabel(f"<b>Mat:</b> {mat}")
        lbl_src = QLabel(f"<font color='#64748B' size='-1'>{parent_src} | {stk_id}</font>")

        l.addWidget(lbl_m)
        l.addWidget(lbl_d)
        l.addWidget(lbl_mat)
        l.addWidget(lbl_src)
        return f

    def _print_stickers(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        dlg = QPrintDialog(printer, self)
        if dlg.exec():
            painter = QPainter(printer)
            self.scroll_widget.render(painter)
            painter.end()
            QMessageBox.information(self, "Stickers Printed", "Labels sent to the selected sticker/label printer.")
