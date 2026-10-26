"""
Multi-Layout Printing, Image Batch Export, and CNC Cuts Exporter for SteelNest Pro
Supports:
1. Printing 1, 2, 4, or 6 layouts per page on any Windows printer / PDF.
2. 1-Click Batch Image Export (All sheets saved as high-resolution PNG/JPG).
3. CNC Text & G-Code cutting sequence export.
4. Color or B&W high-contrast printing modes.
"""
import os
from datetime import datetime
from collections import defaultdict
from typing import List, Optional, Any, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QFileDialog, QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    QProgressBar, QApplication, QLineEdit
)
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPixmap, QPageLayout, QPageSize
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from steel_nest.models.nesting_plan import OptimizationResult, PlateNestPlan, LinearBarPlan


class MultiLayoutPrintDialog(QDialog):
    """Dialog to configure printing 1, 2, 4, or 6 layouts per page and batch image export."""
    def __init__(self, result: OptimizationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("🖨️ Multi-Layout Print & Export — طباعة وتصدير المخططات")
        self.resize(550, 420)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)

        # Print per page configuration
        grp_layout = QGroupBox("توزيع المخططات في الصفحة الواحدة (Layouts per Page)")
        grp_layout_l = QVBoxLayout(grp_layout)

        self.btn_group_per_page = QButtonGroup(self)
        self.rb_1 = QRadioButton("مخطط واحد في الصفحة (1 Layout per page - Large Detail)")
        self.rb_2 = QRadioButton("مخططان في الصفحة (2 Layouts per page)")
        self.rb_4 = QRadioButton("4 مخططات في الصفحة (4 Layouts per page - 2×2 Grid)")
        self.rb_6 = QRadioButton("6 مخططات في الصفحة (6 Layouts per page - 2×3 Grid)")

        self.rb_1.setChecked(True)
        self.btn_group_per_page.addButton(self.rb_1, 1)
        self.btn_group_per_page.addButton(self.rb_2, 2)
        self.btn_group_per_page.addButton(self.rb_4, 4)
        self.btn_group_per_page.addButton(self.rb_6, 6)

        grp_layout_l.addWidget(self.rb_1)
        grp_layout_l.addWidget(self.rb_2)
        grp_layout_l.addWidget(self.rb_4)
        grp_layout_l.addWidget(self.rb_6)
        main_layout.addWidget(grp_layout)

        # Style & Options
        grp_opts = QGroupBox("خيارات العرض والألوان (Display & Colors)")
        grp_opts_l = QHBoxLayout(grp_opts)

        self.chk_bw = QCheckBox("أبيض وأسود (Black & White high contrast)")
        self.chk_bw.setChecked(False)

        self.chk_sizes = QCheckBox("إظهار المقاسات (Dimensions)")
        self.chk_sizes.setChecked(True)

        self.chk_labels = QCheckBox("إظهار أسماء القطع (Marks/Labels)")
        self.chk_labels.setChecked(True)

        grp_opts_l.addWidget(self.chk_bw)
        grp_opts_l.addWidget(self.chk_sizes)
        grp_opts_l.addWidget(self.chk_labels)
        main_layout.addWidget(grp_opts)

        # Batch Export Buttons Box
        grp_batch = QGroupBox("تصدير سريع بنقرة واحدة (1-Click Batch Export)")
        grp_batch_l = QHBoxLayout(grp_batch)

        btn_batch_images = QPushButton("🖼️ حفظ كل المخططات كصور (Save All Images)")
        btn_batch_images.setStyleSheet("background-color: #0891B2; color: white; font-weight: bold; padding: 6px 12px;")
        btn_batch_images.clicked.connect(self._batch_export_images)

        btn_cnc_text = QPushButton("📄 تصدير كود CNC النصي (CNC Cuts Text)")
        btn_cnc_text.setStyleSheet("background-color: #4F46E5; color: white; font-weight: bold; padding: 6px 12px;")
        btn_cnc_text.clicked.connect(self._export_cnc_cuts)

        grp_batch_l.addWidget(btn_batch_images)
        grp_batch_l.addWidget(btn_cnc_text)
        main_layout.addWidget(grp_batch)

        # Progress bar (hidden by default)
        self.prog = QProgressBar()
        self.prog.setVisible(False)
        main_layout.addWidget(self.prog)

        # Dialog Buttons
        btn_row = QHBoxLayout()
        btn_print = QPushButton("🖨️ طباعة المخططات (Print)")
        btn_print.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 8px 20px; font-size: 13px;")
        btn_print.clicked.connect(self._do_print)

        btn_close = QPushButton("إغلاق (Close)")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_print)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        main_layout.addLayout(btn_row)

    def _do_print(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dlg = QPrintDialog(printer, self)
        if not dlg.exec():
            return

        per_page = self.btn_group_per_page.checkedId()
        is_bw = self.chk_bw.isChecked()
        show_sizes = self.chk_sizes.isChecked()
        show_labels = self.chk_labels.isChecked()

        painter = QPainter(printer)
        page_rect = printer.pageLayout().paintRectPixels(printer.resolution())

        # Collect plans to print
        plans_2d = self.result.plate_plans
        plans_1d = self.result.linear_plans

        all_plans = []
        for p in plans_2d:
            all_plans.append(("2D", p))
        for p in plans_1d:
            all_plans.append(("1D", p))

        if not all_plans:
            painter.end()
            QMessageBox.information(self, "تنبيه", "لا توجد مخططات للطباعة.")
            return

        # Determine grid rows and cols
        if per_page == 1:
            grid_r, grid_c = 1, 1
        elif per_page == 2:
            grid_r, grid_c = 2, 1
        elif per_page == 4:
            grid_r, grid_c = 2, 2
        else: # 6
            grid_r, grid_c = 2, 3

        cell_w = page_rect.width() / grid_c
        cell_h = page_rect.height() / grid_r

        plan_idx = 0
        while plan_idx < len(all_plans):
            if plan_idx > 0:
                printer.newPage()

            for r in range(grid_r):
                for c in range(grid_c):
                    if plan_idx >= len(all_plans):
                        break
                    p_type, p_obj = all_plans[plan_idx]
                    target_rect = QRectF(
                        page_rect.left() + c * cell_w + 10,
                        page_rect.top() + r * cell_h + 10,
                        cell_w - 20,
                        cell_h - 20
                    )
                    self._render_plan_to_rect(painter, target_rect, p_type, p_obj, is_bw, show_sizes, show_labels)
                    plan_idx += 1

        painter.end()
        QMessageBox.information(self, "تمت الطباعة", "تم إرسال المخططات المحددة بنجاح إلى الطابعة.")

    def _render_plan_to_rect(
        self,
        painter: QPainter,
        rect: QRectF,
        p_type: str,
        plan: Any,
        is_bw: bool,
        show_sizes: bool,
        show_labels: bool
    ):
        # Draw frame boundary
        painter.save()
        painter.setPen(QPen(QColor("#000000" if is_bw else "#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRect(rect)

        # Title / Repetition header
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#1E293B")))

        rep_str = f" × {plan.repetition_count} Sheets" if getattr(plan, "repetition_count", 1) > 1 else ""
        if p_type == "2D":
            title = f"Plate #{plan.plate_index} ({plan.grade} - {plan.thickness_mm:.0f}mm) [ {plan.plate_length:.0f}×{plan.plate_width:.0f} mm ]{rep_str} — Util: {plan.utilization_pct:.1f}%"
        else:
            title = f"Bar #{plan.bar_index} ({plan.designation}) [ {plan.stock_length:.0f} mm ]{rep_str} — Util: {plan.utilization_pct:.1f}%"
        painter.drawText(rect.adjusted(8, 6, -8, -rect.height() + 24), Qt.AlignmentFlag.AlignLeft, title)

        content_rect = rect.adjusted(15, 30, -15, -15)

        if p_type == "2D":
            pl_len = plan.plate_length
            pl_wid = plan.plate_width
            scale_x = content_rect.width() / max(1.0, pl_len)
            scale_y = content_rect.height() / max(1.0, pl_wid)
            scale = min(scale_x, scale_y) * 0.95

            draw_w = pl_len * scale
            draw_h = pl_wid * scale
            draw_x = content_rect.left() + (content_rect.width() - draw_w) / 2.0
            draw_y = content_rect.top() + (content_rect.height() - draw_h) / 2.0

            # Draw Plate Background (Scrap hatch)
            painter.setBrush(QBrush(QColor("#000000" if is_bw else "#64748B"), Qt.BrushStyle.DiagCrossPattern))
            painter.setPen(QPen(QColor("#000000"), 2))
            painter.drawRect(QRectF(draw_x, draw_y, draw_w, draw_h))

            # Draw Parts
            part_colors = [
                QColor("#FFFFFF"), QColor("#FEF3C7"), QColor("#E0E7FF"),
                QColor("#DCFCE7"), QColor("#EDE9FE"), QColor("#FEE2E2")
            ]

            for idx, pt in enumerate(plan.parts):
                px = draw_x + (pt.y * scale)
                py = draw_y + (pt.x * scale)
                pw = pt.length * scale
                ph = pt.width * scale

                part_rect = QRectF(px, py, pw, ph)
                fill_col = QColor("#FFFFFF") if is_bw else part_colors[idx % len(part_colors)]
                painter.setBrush(QBrush(fill_col))
                painter.setPen(QPen(QColor("#000000" if is_bw else "#16A34A"), 1.5))
                painter.drawRect(part_rect)

                if show_labels and pw > 25 and ph > 15:
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QPen(QColor("#000000")))
                    lbl_text = pt.part_mark
                    if show_sizes:
                        lbl_text += f"\n{pt.length:.0f}×{pt.width:.0f}"
                    painter.drawText(part_rect, Qt.AlignmentFlag.AlignCenter, lbl_text)

        elif p_type == "1D":
            # Draw 1D bar
            bar_len = plan.stock_length
            scale = (content_rect.width() * 0.95) / max(1.0, bar_len)
            bar_h = min(40.0, content_rect.height() * 0.4)
            bar_x = content_rect.left() + (content_rect.width() - bar_len * scale) / 2.0
            bar_y = content_rect.top() + (content_rect.height() - bar_h) / 2.0

            # Raw stock with scrap hatch
            painter.setBrush(QBrush(QColor("#000000" if is_bw else "#64748B"), Qt.BrushStyle.DiagCrossPattern))
            painter.setPen(QPen(QColor("#000000"), 2))
            painter.drawRect(QRectF(bar_x, bar_y, bar_len * scale, bar_h))

            # Segments
            for idx, seg in enumerate(plan.segments):
                sx = bar_x + (seg.start_pos * scale)
                sw = seg.length * scale
                seg_rect = QRectF(sx, bar_y, sw, bar_h)

                painter.setBrush(QBrush(QColor("#FFFFFF") if is_bw else QColor("#DCFCE7")))
                painter.setPen(QPen(QColor("#000000" if is_bw else "#16A34A"), 1.5))
                painter.drawRect(seg_rect)

                if show_labels and sw > 30:
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QPen(QColor("#000000")))
                    lbl = f"{seg.part_mark}\n{seg.length:.0f}" if show_sizes else seg.part_mark
                    painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, lbl)

        painter.restore()

    def _batch_export_images(self):
        """Exports all sheets as numbered PNG images with 1-click."""
        out_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد حفظ الصور (Select Destination Folder)")
        if not out_dir:
            return

        is_bw = self.chk_bw.isChecked()
        show_sizes = self.chk_sizes.isChecked()
        show_labels = self.chk_labels.isChecked()

        saved_count = 0
        # Export 2D Plates
        for idx, pl in enumerate(self.result.plate_plans):
            img_w, img_h = 1920, 1080
            pix = QPixmap(img_w, img_h)
            pix.fill(QColor("#FFFFFF"))
            painter = QPainter(pix)
            self._render_plan_to_rect(
                painter, QRectF(20, 20, img_w - 40, img_h - 40),
                "2D", pl, is_bw, show_sizes, show_labels
            )
            painter.end()

            rep_tag = f"_x{pl.repetition_count}" if pl.repetition_count > 1 else ""
            file_name = f"Sheet_{idx + 1}{rep_tag}_{pl.grade}.png".replace(" ", "_")
            full_path = os.path.join(out_dir, file_name)
            pix.save(full_path, "PNG")
            saved_count += 1

        # Export 1D Bars
        for idx, bar in enumerate(self.result.linear_plans):
            img_w, img_h = 1920, 600
            pix = QPixmap(img_w, img_h)
            pix.fill(QColor("#FFFFFF"))
            painter = QPainter(pix)
            self._render_plan_to_rect(
                painter, QRectF(20, 20, img_w - 40, img_h - 40),
                "1D", bar, is_bw, show_sizes, show_labels
            )
            painter.end()

            rep_tag = f"_x{bar.repetition_count}" if bar.repetition_count > 1 else ""
            file_name = f"Bar_{idx + 1}{rep_tag}_{bar.designation}.png".replace(" ", "_")
            full_path = os.path.join(out_dir, file_name)
            pix.save(full_path, "PNG")
            saved_count += 1

        QMessageBox.information(
            self,
            "تم تصدير الصور بنجاح",
            f"تم حفظ {saved_count} صورة عالية الدقة للمخططات في:\n{out_dir}"
        )

    def _export_cnc_cuts(self):
        """Exports CNC saw cuts definition and coordinates in text format."""
        path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف كود التقطيع (Save CNC Cuts)", "CNC_Cut_Sequence.txt", "Text Files (*.txt)")
        if not path:
            return

        lines = []
        lines.append("=================================================================")
        lines.append(f"SteelNest Pro — CNC Saw & Cutting Sequence Definition")
        lines.append(f"Project: {self.result.project_id or 'PRJ-CURRENT'} | Date: {self.result.created_at}")
        lines.append("=================================================================\n")

        # 2D Plate Cuts
        if self.result.plate_plans:
            lines.append("--- 2D PLATE & SHEET CUTTING SEQUENCES ---\n")
            for pl in self.result.plate_plans:
                lines.append(f"SHEET #{pl.plate_index} | Stock: {pl.stock_id} ({pl.grade} - {pl.thickness_mm:.0f}mm) | Size: {pl.plate_length:.0f} x {pl.plate_width:.0f} mm | Repetition: {pl.repetition_count}")
                lines.append(f"Total Cut Distance: {pl.total_cut_length:.1f} mm | Kerf: {pl.kerf} mm | Margin: {pl.margin} mm")
                lines.append(f"Number of Parts Nested: {len(pl.parts)}")
                lines.append("-" * 65)
                lines.append("CUT_ID | STAGE | DIRECTION | START_X  | START_Y  | END_X    | END_Y    | LENGTH")
                lines.append("-" * 65)

                if pl.cut_lines:
                    for c_idx, c in enumerate(pl.cut_lines):
                        lines.append(f"{c_idx+1:06d} | {c.get('stage', 1):5d} | {c.get('type', 'CUT'):9s} | {c.get('x1', 0.0):8.1f} | {c.get('y1', 0.0):8.1f} | {c.get('x2', 0.0):8.1f} | {c.get('y2', 0.0):8.1f} | {c.get('length', 0.0):7.1f}")
                else:
                    # Generate contour cuts for parts
                    c_num = 1
                    for pt in pl.parts:
                        lines.append(f"{c_num:06d} |     1 | PART_BOX  | {pt.y:8.1f} | {pt.x:8.1f} | {pt.y+pt.length:8.1f} | {pt.x+pt.width:8.1f} | {2*(pt.length+pt.width):7.1f} (Mark: {pt.part_mark})")
                        c_num += 1
                lines.append("\n")

        # 1D Linear Bar Cuts
        if self.result.linear_plans:
            lines.append("--- 1D LINEAR PROFILE CUTTING SEQUENCES ---\n")
            for bar in self.result.linear_plans:
                lines.append(f"BAR #{bar.bar_index} | Section: {bar.designation} ({bar.grade}) | Length: {bar.stock_length:.0f} mm | Repetition: {bar.repetition_count}")
                lines.append(f"Trim Start: {bar.trim_start:.1f} mm | Kerf: {bar.kerf:.1f} mm | Usable Remnant: {bar.raw_remnant_length:.1f} mm")
                lines.append("-" * 65)
                lines.append("STEP | PART_MARK | CUT_LENGTH | START_POS | END_POS | SAW_KERF")
                lines.append("-" * 65)
                for s_idx, seg in enumerate(bar.segments):
                    lines.append(f"{s_idx+1:04d} | {seg.part_mark:9s} | {seg.length:10.1f} | {seg.start_pos:9.1f} | {seg.end_pos:7.1f} | {seg.kerf_after:8.1f}")
                lines.append("\n")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        QMessageBox.information(
            self,
            "تم تصدير كود CNC بنجاح",
            f"تم حفظ ملف تسلسل التقطيع بنجاح في:\n{path}"
        )


class BatchImageExportDialog(QDialog):
    """Standalone dialog triggered directly from toolbar for 1-click batch image export."""
    def __init__(self, result: OptimizationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("🖼️ Batch Image Export — حفظ جميع المخططات كصور")
        self.resize(460, 240)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel("تصدير جميع ألواح الصاج وأعواد الاستيل كصور عالية الدقة (1920×1080 PNG):\nExport all plate and bar layouts as individual high-resolution PNG images.")
        lbl.setWordWrap(True)
        lbl.setFont(QFont("Segoe UI", 9))
        layout.addWidget(lbl)

        self.chk_bw = QCheckBox("أبيض وأسود عالي التباين (Black & White high contrast)")
        self.chk_sizes = QCheckBox("إظهار المقاسات والأبعاد (Show sizes / dimensions)")
        self.chk_sizes.setChecked(True)
        self.chk_labels = QCheckBox("إظهار أسماء ومارك القطع (Show part labels)")
        self.chk_labels.setChecked(True)

        layout.addWidget(self.chk_bw)
        layout.addWidget(self.chk_sizes)
        layout.addWidget(self.chk_labels)

        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        btn_export = QPushButton("📁 اختر المجلد وابدأ التصدير (Export All)")
        btn_export.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 7px 18px; border-radius: 4px;")
        btn_export.clicked.connect(self._run_export)
        btn_cancel = QPushButton("إلغاء (Cancel)")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_export)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _run_export(self):
        printer_dlg = MultiLayoutPrintDialog(self.result, self)
        printer_dlg.chk_bw.setChecked(self.chk_bw.isChecked())
        printer_dlg.chk_sizes.setChecked(self.chk_sizes.isChecked())
        printer_dlg.chk_labels.setChecked(self.chk_labels.isChecked())
        printer_dlg._batch_export_images()
        self.accept()


class CNCCutSequenceDialog(QDialog):
    """Standalone dialog triggered directly from toolbar for CNC coordinates export."""
    def __init__(self, result: OptimizationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("📄 CNC Cut Coordinates & Sequences — تسلسل التقطيع")
        self.resize(500, 220)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        total_dist = sum(pl.total_cut_distance for pl in self.result.plate_plans)
        lbl = QLabel(
            f"تصدير تسلسل وإحداثيات مسارات ماكينات التقطيع ومسافة مشوار المنشار/الليزر:\n"
            f"• إجمالي مسافة التقطيع (Total Cut Distance): {total_dist:.1f} mm\n"
            f"• عدد ألواح الصاج: {len(self.result.plate_plans)} | عدد الأعواد: {len(self.result.linear_plans)}"
        )
        lbl.setWordWrap(True)
        lbl.setFont(QFont("Segoe UI", 9))
        layout.addWidget(lbl)

        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        btn_save = QPushButton("💾 حفظ ملف الإحداثيات (Save CNC Text File)")
        btn_save.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 7px 18px; border-radius: 4px;")
        btn_save.clicked.connect(self._run_save)
        btn_cancel = QPushButton("إلغاء (Cancel)")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _run_save(self):
        printer_dlg = MultiLayoutPrintDialog(self.result, self)
        printer_dlg._export_cnc_cuts()
        self.accept()


class CuttingPrintPdfDialog(QDialog):
    """
    Unified, smooth Print & PDF Export dialog for SteelNest Pro.
    Allows:
    - Direct Windows Printing or saving high-resolution vector PDF
    - Selective printing: All patterns, Current pattern only, or Custom page range (e.g. 1-3, 5)
    - Paper size & orientation selection
    - Robust exception handling so clicking Print never crashes the app
    """
    def __init__(self, result: OptimizationResult, active_mode: str = "2D", current_idx: int = 0, parent=None):
        super().__init__(parent)
        self.result = result
        self.active_mode = active_mode  # "2D" or "1D"
        self.current_idx = max(0, current_idx)
        self.setWindowTitle("🖨️ Print & PDF Export — WafraCut Pro")
        self.resize(560, 560)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Destination
        grp_dest = QGroupBox("جهة الإخراج والطباعة (Output Destination)")
        grp_dest_l = QVBoxLayout(grp_dest)
        grp_dest_l.setSpacing(5)

        self.btn_group_dest = QButtonGroup(self)
        self.rb_dest_pdf = QRadioButton("📄 حفظ كملف PDF عالي الجودة (Export to PDF File)")
        self.rb_dest_pdf.setChecked(True)
        self.rb_dest_print = QRadioButton("🖨️ إرسال إلى الطابعة الفعلية (Send to Physical Printer)")

        self.btn_group_dest.addButton(self.rb_dest_pdf, 1)
        self.btn_group_dest.addButton(self.rb_dest_print, 2)
        grp_dest_l.addWidget(self.rb_dest_pdf)
        grp_dest_l.addWidget(self.rb_dest_print)
        main_layout.addWidget(grp_dest)

        # 2. Content Selection (Print Diagrams, Results Tables, and Statistics)
        grp_content = QGroupBox("محتويات التقرير والطباعة (What to Include in Print / PDF)")
        grp_content_l = QVBoxLayout(grp_content)
        grp_content_l.setSpacing(5)

        self.chk_inc_summary = QCheckBox("📄 طباعة ملخص الإحصائيات والهالك (Summary & KPI Statistics)")
        self.chk_inc_summary.setChecked(True)
        self.chk_inc_cutlist = QCheckBox("📋 طباعة جداول حصر وتفاصيل القطع (Detailed Cut List Table)")
        self.chk_inc_cutlist.setChecked(True)
        self.chk_inc_diagrams = QCheckBox("📐 طباعة المخططات والرسومات التخطيطية (Cutting Layout Diagrams)")
        self.chk_inc_diagrams.setChecked(True)

        grp_content_l.addWidget(self.chk_inc_summary)
        grp_content_l.addWidget(self.chk_inc_cutlist)
        grp_content_l.addWidget(self.chk_inc_diagrams)
        main_layout.addWidget(grp_content)

        # 3. Pages to Print for Diagrams
        plans = self.result.plate_plans if self.active_mode == "2D" else self.result.linear_plans
        if not plans:
            plans = self.result.plate_plans or self.result.linear_plans
        total_n = len(plans) if plans else 1

        grp_pages = QGroupBox("تحديد المخططات المراد طباعتها (Layout Selection)")
        grp_pages_l = QVBoxLayout(grp_pages)
        grp_pages_l.setSpacing(5)

        self.btn_group_pages = QButtonGroup(self)
        self.rb_page_all = QRadioButton(f"🔘 جميع المخططات المتاحة (All Patterns — {total_n} مخطط)")
        self.rb_page_all.setChecked(True)

        curr_num = min(self.current_idx + 1, total_n)
        self.rb_page_current = QRadioButton(f"🔘 المخطط الحالي المعروض فقط (Current Pattern #{curr_num})")

        h_custom = QHBoxLayout()
        self.rb_page_custom = QRadioButton("🔘 نطاق صفحات مخصص (Custom Range):")
        self.txt_custom_range = QLineEdit()
        self.txt_custom_range.setPlaceholderText(f"مثال: 1-{min(3, total_n)} أو 1, 3")
        self.txt_custom_range.setEnabled(False)
        self.rb_page_custom.toggled.connect(lambda chk: self.txt_custom_range.setEnabled(chk))
        h_custom.addWidget(self.rb_page_custom)
        h_custom.addWidget(self.txt_custom_range)

        self.btn_group_pages.addButton(self.rb_page_all, 1)
        self.btn_group_pages.addButton(self.rb_page_current, 2)
        self.btn_group_pages.addButton(self.rb_page_custom, 3)

        grp_pages_l.addWidget(self.rb_page_all)
        grp_pages_l.addWidget(self.rb_page_current)
        grp_pages_l.addLayout(h_custom)
        main_layout.addWidget(grp_pages)

        # 4. Paper & Format
        grp_format = QGroupBox("إعدادات الورق والمظهر (Paper & Display)")
        grp_format_l = QVBoxLayout(grp_format)
        grp_format_l.setSpacing(6)

        h_po = QHBoxLayout()
        lbl_paper = QLabel("حجم الورق:")
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(["A4", "A3"])
        h_po.addWidget(lbl_paper)
        h_po.addWidget(self.combo_paper)

        h_po.addSpacing(20)
        lbl_orient = QLabel("الاتجاه:")
        self.rb_orient_land = QRadioButton("أفقي (Landscape)")
        self.rb_orient_land.setChecked(True)
        self.rb_orient_port = QRadioButton("رأسي (Portrait)")
        self.btn_orient = QButtonGroup(self)
        self.btn_orient.addButton(self.rb_orient_land, 1)
        self.btn_orient.addButton(self.rb_orient_port, 2)
        h_po.addWidget(lbl_orient)
        h_po.addWidget(self.rb_orient_land)
        h_po.addWidget(self.rb_orient_port)
        h_po.addStretch()
        grp_format_l.addLayout(h_po)

        h_chk = QHBoxLayout()
        self.chk_sizes = QCheckBox("إظهار المقاسات (Sizes)")
        self.chk_sizes.setChecked(True)
        self.chk_labels = QCheckBox("إظهار الأكواد (Labels)")
        self.chk_labels.setChecked(True)
        self.chk_bw = QCheckBox("🎨 نمط أبيض وأسود (B&W)")
        self.chk_bw.setChecked(False)

        h_chk.addWidget(self.chk_sizes)
        h_chk.addWidget(self.chk_labels)
        h_chk.addWidget(self.chk_bw)
        h_chk.addStretch()
        grp_format_l.addLayout(h_chk)
        main_layout.addWidget(grp_format)

        # 5. Action Buttons
        btns = QHBoxLayout()
        btn_action = QPushButton("▶ تنفيذ الطباعة / التصدير")
        btn_action.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_action.setStyleSheet("background-color: #16A34A; color: white; padding: 7px 22px; border-radius: 4px;")
        btn_action.clicked.connect(self._do_print_or_pdf)

        btn_cancel = QPushButton("إلغاء (Cancel)")
        btn_cancel.clicked.connect(self.reject)

        btns.addWidget(btn_action)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        main_layout.addLayout(btns)

    def _do_print_or_pdf(self):
        try:
            plans = self.result.plate_plans if self.active_mode == "2D" else self.result.linear_plans
            if not plans:
                plans = self.result.plate_plans or self.result.linear_plans
            if not plans:
                QMessageBox.warning(self, "تنبيه", "لا توجد مخططات تقطيع جاهزة للطباعة.")
                return

            need_summary = self.chk_inc_summary.isChecked()
            need_cutlist = self.chk_inc_cutlist.isChecked()
            need_diagrams = self.chk_inc_diagrams.isChecked()

            if not (need_summary or need_cutlist or need_diagrams):
                QMessageBox.warning(self, "تنبيه", "يرجى اختيار عنصر واحد على الأقل للطباعة (ملخص، جدول قطع، أو مخططات).")
                return

            total_n = len(plans)
            selected_indices = []

            if need_diagrams:
                if self.rb_page_current.isChecked():
                    idx = min(self.current_idx, total_n - 1)
                    selected_indices = [idx]
                elif self.rb_page_custom.isChecked():
                    txt = self.txt_custom_range.text().strip()
                    if not txt:
                        QMessageBox.warning(self, "تنبيه", "يرجى كتابة أرقام الصفحات المطلوبة (مثال: 1-3 أو 1, 3).")
                        return
                    for part in txt.split(','):
                        part = part.strip()
                        if '-' in part:
                            s_str, e_str = part.split('-', 1)
                            if s_str.strip().isdigit() and e_str.strip().isdigit():
                                s = int(s_str.strip())
                                e = int(e_str.strip())
                                for p in range(min(s, e), max(s, e) + 1):
                                    if 1 <= p <= total_n and (p - 1) not in selected_indices:
                                        selected_indices.append(p - 1)
                        elif part.isdigit():
                            p = int(part)
                            if 1 <= p <= total_n and (p - 1) not in selected_indices:
                                selected_indices.append(p - 1)
                    selected_indices.sort()
                    if not selected_indices:
                        QMessageBox.warning(self, "تنبيه", f"لم يتم العثور على صفحات صحيحة في النطاق المحدد (1 إلى {total_n}).")
                        return
                else:
                    selected_indices = list(range(total_n))

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            is_landscape = self.rb_orient_land.isChecked()
            printer.setPageOrientation(QPageLayout.Orientation.Landscape if is_landscape else QPageLayout.Orientation.Portrait)
            is_a4 = (self.combo_paper.currentText() == "A4")
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4 if is_a4 else QPageSize.PageSizeId.A3))

            is_pdf = self.rb_dest_pdf.isChecked()
            out_pdf_path = ""
            if is_pdf:
                default_name = f"WafraCut_Full_Cutting_Report_{self.active_mode}.pdf"
                path, _ = QFileDialog.getSaveFileName(self, "Save Complete Report PDF", default_name, "PDF Files (*.pdf)")
                if not path:
                    return
                out_pdf_path = path
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(path)
            else:
                dlg = QPrintDialog(printer, self)
                if not dlg.exec():
                    return

            painter = QPainter(printer)
            page_rect = printer.pageLayout().paintRectPixels(printer.resolution())

            is_bw = self.chk_bw.isChecked()
            show_sizes = self.chk_sizes.isChecked()
            show_labels = self.chk_labels.isChecked()

            first_page = True
            total_pages_printed = 0

            # 1. Summary & Statistics Page
            if need_summary:
                self._render_summary_page(painter, page_rect, plans, is_landscape, is_bw)
                first_page = False
                total_pages_printed += 1

            # 2. Detailed Cut List Page
            if need_cutlist:
                if not first_page:
                    printer.newPage()
                self._render_cutlist_page(painter, page_rect, is_landscape, is_bw)
                first_page = False
                total_pages_printed += 1

            # 3. Graphical Diagrams Pages
            if need_diagrams and selected_indices:
                multi_helper = MultiLayoutPrintDialog(self.result, self)
                for p_idx in selected_indices:
                    if not first_page:
                        printer.newPage()
                    first_page = False
                    plan = plans[p_idx]
                    p_type = "2D" if isinstance(plan, PlateNestPlan) or hasattr(plan, "plate_width") else "1D"
                    target_rect = QRectF(page_rect.left() + 20, page_rect.top() + 20, page_rect.width() - 40, page_rect.height() - 40)
                    multi_helper._render_plan_to_rect(painter, target_rect, p_type, plan, is_bw, show_sizes, show_labels)
                    total_pages_printed += 1

            painter.end()

            if is_pdf:
                QMessageBox.information(self, "تم الحفظ بنجاح", f"تم تصدير ملف الـ PDF الشامل بنجاح ({total_pages_printed} صفحة تشمل المخططات والنتائج):\n{out_pdf_path}")
            else:
                QMessageBox.information(self, "تمت الطباعة", f"تم إرسال {total_pages_printed} صفحة بنجاح إلى الطابعة.")
            self.accept()

        except Exception as ex:
            QMessageBox.critical(self, "خطأ في الطباعة", f"حدث خطأ أثناء محاولة الطباعة أو التصدير:\n{str(ex)}")

    def _render_summary_page(self, painter: QPainter, page_rect: QRectF, plans: list, is_landscape: bool, is_bw: bool):
        """Renders the comprehensive workshop Summary & KPI page matching image media_1792951567795_9eb646e9.png."""
        painter.save()
        w = page_rect.width()
        h = page_rect.height()
        ox = page_rect.left()
        oy = page_rect.top()

        margin_x = ox + w * 0.04
        margin_y = oy + h * 0.04
        content_w = w - (w * 0.08)

        # 1. Header Banner
        header_h = 420
        header_rect = QRectF(margin_x, margin_y, content_w, header_h)
        painter.setBrush(QBrush(QColor("#FFFFFF" if is_bw else "#1E3A8A")))
        painter.setPen(QPen(QColor("#000000"), 2))
        painter.drawRect(header_rect)

        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#FFFFFF")))
        title = f"WafraCut Pro — تقرير تشغيل وتقطيع الورشة ({self.active_mode} Workshop Cutting Plan)"
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, title)

        # Subtitle Info
        sub_y = margin_y + header_h + 80
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#475569")))
        proj_name = self.result.project_id or "CP-01"
        sub_text = f"Project: {proj_name}   |   Mode: {self.active_mode} Nesting Optimization   |   Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        painter.drawText(QRectF(margin_x, sub_y, content_w, 200), Qt.AlignmentFlag.AlignLeft, sub_text)

        # 2. KPI Summary Boxes (4 cards)
        kpi_y = sub_y + 240
        kpi_h = 450
        card_w = (content_w - 300) / 4.0
        kpis = [
            ("نسبة الاستغلال (Utilization)", f"{self.result.overall_utilization_pct:.2f}%", "#DCFCE7"),
            ("إجمالي الخام (Stock Consumed)", f"{len(plans)} Units", "#E0E7FF"),
            ("نسبة الهالك (Scrap Waste)", f"{self.result.overall_waste_pct:.2f}%", "#FEE2E2"),
            ("عدد القطع (Pieces Cut)", f"{self.result.total_parts_nested} pcs", "#FEF3C7"),
        ]
        for idx, (label, val, col) in enumerate(kpis):
            cx = margin_x + idx * (card_w + 100)
            card_rect = QRectF(cx, kpi_y, card_w, kpi_h)
            painter.setBrush(QBrush(QColor("#FFFFFF" if is_bw else col)))
            painter.setPen(QPen(QColor("#000000" if is_bw else "#94A3B8"), 2))
            painter.drawRect(card_rect)

            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(QColor("#000000" if is_bw else "#475569")))
            painter.drawText(QRectF(cx + 40, kpi_y + 40, card_w - 80, 160), Qt.AlignmentFlag.AlignCenter, label)

            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#000000" if is_bw else "#0F172A")))
            painter.drawText(QRectF(cx + 40, kpi_y + 200, card_w - 80, 220), Qt.AlignmentFlag.AlignCenter, val)

        # 3. Main Summary Table (matching Image media_1792951567795_9eb646e9.png)
        table_y = kpi_y + kpi_h + 150
        if self.active_mode == "2D":
            cols = [
                ("#", 0.04, Qt.AlignmentFlag.AlignCenter),
                ("Length ▲", 0.09, Qt.AlignmentFlag.AlignCenter),
                ("Width", 0.09, Qt.AlignmentFlag.AlignCenter),
                ("Quantity", 0.07, Qt.AlignmentFlag.AlignCenter),
                ("Material", 0.11, Qt.AlignmentFlag.AlignCenter),
                ("Label", 0.12, Qt.AlignmentFlag.AlignCenter),
                ("PIECES", 0.24, Qt.AlignmentFlag.AlignLeft),
                ("Waste", 0.24, Qt.AlignmentFlag.AlignLeft),
            ]
        else:
            cols = [
                ("#", 0.04, Qt.AlignmentFlag.AlignCenter),
                ("Length ▲", 0.12, Qt.AlignmentFlag.AlignCenter),
                ("Quantity", 0.08, Qt.AlignmentFlag.AlignCenter),
                ("Material", 0.14, Qt.AlignmentFlag.AlignCenter),
                ("Label", 0.14, Qt.AlignmentFlag.AlignCenter),
                ("PIECES", 0.24, Qt.AlignmentFlag.AlignLeft),
                ("Waste", 0.24, Qt.AlignmentFlag.AlignLeft),
            ]

        th_h = 320
        cur_x = margin_x
        for name, pct, align in cols:
            cw = content_w * pct
            r = QRectF(cur_x, table_y, cw, th_h)
            painter.setBrush(QBrush(QColor("#E2E8F0" if is_bw else "#C6D9F1")))
            painter.setPen(QPen(QColor("#000000" if is_bw else "#94A8C6"), 2))
            painter.drawRect(r)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#000000")))
            painter.drawText(r.adjusted(20, 20, -20, -20), Qt.AlignmentFlag.AlignCenter, name)
            cur_x += cw

        # Data Rows
        row_y = table_y + th_h
        for r_idx, plan in enumerate(plans):
            if self.active_mode == "2D":
                pieces_dict = defaultdict(int)
                for pt in plan.parts:
                    key = f"{pt.length:.0f}x{pt.width:.0f}"
                    pieces_dict[key] += 1
                pieces_lines = [f"{cnt}x - {k}" for k, cnt in sorted(pieces_dict.items(), key=lambda x: -x[1])]
                pieces_txt = "\n".join(pieces_lines[:4])

                waste_lines = []
                if hasattr(plan, "waste_rects") and plan.waste_rects:
                    w_dict = defaultdict(int)
                    for wr in plan.waste_rects:
                        wl, ww = wr.get("length", 0), wr.get("width", 0)
                        if wl > 5 and ww > 5:
                            w_dict[f"{wl:.0f}x{ww:.0f}"] += 1
                    waste_lines = [f"{cnt}x - {k}" for k, cnt in sorted(w_dict.items(), key=lambda x: -x[1])]
                if not waste_lines:
                    wa = getattr(plan, "waste_area", 0.0)
                    waste_lines = [f"Waste: {wa/1_000_000.0:.2f} m²"]
                waste_txt = "\n".join(waste_lines[:4])

                desig = f"PL {int(plan.thickness_mm) if plan.thickness_mm.is_integer() else plan.thickness_mm}" if plan.thickness_mm > 0 else (plan.grade or "PL")
                vals = [
                    f"{plan.plate_index}",
                    f"{plan.plate_length:.0f}",
                    f"{plan.plate_width:.0f}",
                    f"{plan.repetition_count}",
                    desig,
                    plan.stock_id or plan.grade or "Sheet",
                    pieces_txt,
                    waste_txt
                ]
            else:
                pieces_dict = defaultdict(int)
                for seg in plan.segments:
                    pieces_dict[f"{seg.length:.0f}"] += 1
                pieces_lines = [f"{cnt}x - {k}" for k, cnt in sorted(pieces_dict.items(), key=lambda x: -x[1])]
                pieces_txt = "\n".join(pieces_lines[:4])

                rem = plan.raw_remnant_length
                waste_txt = f"1x - {rem:.0f}" if rem > 0 else "0 mm"
                vals = [
                    f"{plan.bar_index}",
                    f"{plan.stock_length:.0f}",
                    f"{plan.repetition_count}",
                    plan.designation,
                    plan.stock_id or plan.grade or "Bar",
                    pieces_txt,
                    waste_txt
                ]

            max_lines = max(1, pieces_txt.count("\n") + 1, waste_txt.count("\n") + 1)
            row_h = max(380, max_lines * 180 + 80)

            if row_y + row_h > (oy + h) - 500:
                break  # page boundary limit

            cur_x = margin_x
            bg_col = QColor("#FFFFFF") if r_idx % 2 == 0 else QColor("#F8FAFC")
            for c_idx, (name, pct, align) in enumerate(cols):
                cw = content_w * pct
                r = QRectF(cur_x, row_y, cw, row_h)
                painter.setBrush(QBrush(QColor("#DCE6F1") if c_idx == 0 and not is_bw else bg_col))
                painter.setPen(QPen(QColor("#000000" if is_bw else "#CBD5E1"), 1.5))
                painter.drawRect(r)

                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold if c_idx == 0 else QFont.Weight.Normal))
                painter.setPen(QPen(QColor("#000000")))
                val_str = vals[c_idx]
                flags = align | (Qt.AlignmentFlag.AlignVCenter if "\n" not in val_str else Qt.AlignmentFlag.AlignTop)
                painter.drawText(r.adjusted(30, 20, -30, -20), flags, val_str)
                cur_x += cw

            row_y += row_h

        # Footer
        footer_r = QRectF(margin_x, oy + h - margin_y / 2 - 150, content_w, 180)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#64748B")))
        painter.drawText(footer_r, Qt.AlignmentFlag.AlignLeft, "جميع الحقوق محفوظة (المهندس محمد جمال محي) | WafraCut Pro v1.0.0")
        painter.drawText(footer_r, Qt.AlignmentFlag.AlignRight, "Workshop Report • Summary")

        painter.restore()

    def _render_cutlist_page(self, painter: QPainter, page_rect: QRectF, is_landscape: bool, is_bw: bool):
        """Renders the detailed Cut List & Parts Allocation Table."""
        painter.save()
        w = page_rect.width()
        h = page_rect.height()
        ox = page_rect.left()
        oy = page_rect.top()

        margin_x = ox + w * 0.04
        margin_y = oy + h * 0.04
        content_w = w - (w * 0.08)

        # Header Banner
        header_h = 420
        header_rect = QRectF(margin_x, margin_y, content_w, header_h)
        painter.setBrush(QBrush(QColor("#FFFFFF" if is_bw else "#1E3A8A")))
        painter.setPen(QPen(QColor("#000000"), 2))
        painter.drawRect(header_rect)

        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#FFFFFF")))
        title = f"WafraCut Pro — جدول حصر وتوزيع قطع التشغيل التفصيلي (Detailed Cut List)"
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, title)

        table_y = margin_y + header_h + 100
        if self.active_mode == "2D":
            cols = [
                ("#", 0.05, Qt.AlignmentFlag.AlignCenter),
                ("Part Mark / Tag", 0.20, Qt.AlignmentFlag.AlignLeft),
                ("Length (mm)", 0.12, Qt.AlignmentFlag.AlignCenter),
                ("Width (mm)", 0.12, Qt.AlignmentFlag.AlignCenter),
                ("Qty Required", 0.11, Qt.AlignmentFlag.AlignCenter),
                ("Material / Grade", 0.16, Qt.AlignmentFlag.AlignLeft),
                ("Allocated Plate Pattern #", 0.24, Qt.AlignmentFlag.AlignLeft),
            ]
        else:
            cols = [
                ("#", 0.05, Qt.AlignmentFlag.AlignCenter),
                ("Part Mark / Tag", 0.24, Qt.AlignmentFlag.AlignLeft),
                ("Length (mm)", 0.15, Qt.AlignmentFlag.AlignCenter),
                ("Qty Required", 0.12, Qt.AlignmentFlag.AlignCenter),
                ("Section / Designation", 0.20, Qt.AlignmentFlag.AlignLeft),
                ("Allocated Bar Pattern #", 0.24, Qt.AlignmentFlag.AlignLeft),
            ]

        th_h = 320
        cur_x = margin_x
        for name, pct, align in cols:
            cw = content_w * pct
            r = QRectF(cur_x, table_y, cw, th_h)
            painter.setBrush(QBrush(QColor("#E2E8F0" if is_bw else "#C6D9F1")))
            painter.setPen(QPen(QColor("#000000" if is_bw else "#94A8C6"), 2))
            painter.drawRect(r)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#000000")))
            painter.drawText(r.adjusted(20, 20, -20, -20), Qt.AlignmentFlag.AlignCenter, name)
            cur_x += cw

        # Aggregate Cut Items
        row_y = table_y + th_h
        items_rows = []
        if self.active_mode == "2D":
            for pl in self.result.plate_plans:
                p_idx = pl.plate_index
                for pt in pl.parts:
                    items_rows.append((
                        pt.part_mark, f"{pt.length:.0f}", f"{pt.width:.0f}", "1",
                        pl.grade or "PL", f"Sheet #{p_idx} (x{pl.repetition_count})"
                    ))
        else:
            for bar in self.result.linear_plans:
                b_idx = bar.bar_index
                for seg in bar.segments:
                    items_rows.append((
                        seg.part_mark, f"{seg.length:.0f}", "1",
                        bar.designation, f"Bar #{b_idx} (x{bar.repetition_count})"
                    ))

        for r_idx, row_data in enumerate(items_rows):
            row_h = 280
            if row_y + row_h > (oy + h) - 500:
                break
            cur_x = margin_x
            bg_col = QColor("#FFFFFF") if r_idx % 2 == 0 else QColor("#F8FAFC")
            row_vals = [f"{r_idx + 1}"] + list(row_data)

            for c_idx, (name, pct, align) in enumerate(cols):
                cw = content_w * pct
                r = QRectF(cur_x, row_y, cw, row_h)
                painter.setBrush(QBrush(QColor("#DCE6F1") if c_idx == 0 and not is_bw else bg_col))
                painter.setPen(QPen(QColor("#000000" if is_bw else "#CBD5E1"), 1.5))
                painter.drawRect(r)

                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold if c_idx == 0 else QFont.Weight.Normal))
                painter.setPen(QPen(QColor("#000000")))
                painter.drawText(r.adjusted(30, 20, -30, -20), align | Qt.AlignmentFlag.AlignVCenter, row_vals[c_idx])
                cur_x += cw
            row_y += row_h

        # Footer
        footer_r = QRectF(margin_x, oy + h - margin_y / 2 - 150, content_w, 180)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#000000" if is_bw else "#64748B")))
        painter.drawText(footer_r, Qt.AlignmentFlag.AlignLeft, "جميع الحقوق محفوظة (المهندس محمد جمال محي) | WafraCut Pro v1.0.0")
        painter.drawText(footer_r, Qt.AlignmentFlag.AlignRight, "Workshop Report • Cut List")

        painter.restore()

