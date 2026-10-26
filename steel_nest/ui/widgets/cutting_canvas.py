"""
Cutting Canvas Widget for SteelNest Pro
Renders interactive, CAD-grade cutting layouts for 2D Plates/Sheets and 1D Linear Stock.
Features:
- Dimension callouts (Sizes Piece)
- Labels & part marks
- Color Mode (Vibrant pastels & green seams) or B&W Mode (High-contrast engineering)
- Cross-hatched scrap/remnant areas
- Grouped repetition count badge (e.g. Quantity: 5 sheets)
- Total saw cut distance in caption
- Multi-zoom levels (Fit, 50%, 75%, 100%, 125%, 150%, 200%, 300%)
"""
from typing import Optional, Union, List
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPaintEvent, QPolygonF, QMouseEvent
)
from PyQt6.QtCore import Qt, QRectF, QPointF

from steel_nest.models.nesting_plan import PlateNestPlan, LinearBarPlan

# Colorful pastel palette for distinguishable parts
PART_PASTEL_COLORS = [
    QColor("#FEF3C7"), # Soft warm yellow
    QColor("#E0E7FF"), # Soft blue
    QColor("#DCFCE7"), # Mint green
    QColor("#EDE9FE"), # Lavender purple
    QColor("#FEE2E2"), # Soft rose
    QColor("#CFFAFE"), # Soft cyan
    QColor("#FFEDD5"), # Soft peach
    QColor("#F3E8FF"), # Soft lilac
]

class CuttingCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plan_2d: Optional[PlateNestPlan] = None
        self.plan_1d: Optional[LinearBarPlan] = None
        self.mode: str = "2D" # "2D" or "1D"

        self.show_sizes: bool = True
        self.show_labels: bool = True
        self.color_mode: str = "COLOR" # "COLOR" or "BW"
        self.zoom_factor: float = 1.0
        self.fit_to_window: bool = True

        self.setMinimumSize(450, 350)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #FFFFFF;")

    def set_2d_plan(self, plan: Optional[PlateNestPlan]):
        self.plan_2d = plan
        self.plan_1d = None
        self.mode = "2D"
        self.update()

    def set_1d_plan(self, plan: Optional[LinearBarPlan]):
        self.plan_1d = plan
        self.plan_2d = None
        self.mode = "1D"
        self.update()

    def set_display_options(
        self,
        show_sizes: bool,
        show_labels: bool,
        zoom_factor: float = 1.0,
        fit: bool = True,
        color_mode: str = "COLOR"
    ):
        self.show_sizes = show_sizes
        self.show_labels = show_labels
        self.zoom_factor = zoom_factor
        self.fit_to_window = fit
        self.color_mode = color_mode
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if self.mode == "2D" and self.plan_2d:
            self._paint_2d_plate(painter)
        elif self.mode == "1D" and self.plan_1d:
            self._paint_1d_bar(painter)
        else:
            self._paint_empty_state(painter)

    def _paint_empty_state(self, painter: QPainter):
        painter.setPen(QPen(QColor("#94A3B8"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(self.rect().adjusted(20, 20, -20, -20))
        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QPen(QColor("#64748B")))
        painter.drawText(
            self.rect(), Qt.AlignmentFlag.AlignCenter,
            "اضغط على زر ▶ Start لبدء التحسين وعرض المخطط هنا\nPress '▶ Start' to optimize and view cutting layout"
        )

    def _paint_2d_plate(self, painter: QPainter):
        plan = self.plan_2d
        if not plan or plan.plate_length <= 0 or plan.plate_width <= 0:
            return

        w_widget = self.width()
        h_widget = self.height()

        margin_top = 45
        margin_left = 65
        margin_right = 35
        margin_bottom = 50

        avail_w = max(50, w_widget - margin_left - margin_right)
        avail_h = max(50, h_widget - margin_top - margin_bottom)

        if self.fit_to_window:
            scale_x = avail_w / plan.plate_length
            scale_y = avail_h / plan.plate_width
            scale = min(scale_x, scale_y)
        else:
            base_scale = min(avail_w / plan.plate_length, avail_h / plan.plate_width)
            scale = base_scale * self.zoom_factor

        draw_w = plan.plate_length * scale
        draw_h = plan.plate_width * scale

        offset_x = margin_left + max(0, (avail_w - draw_w) / 2.0)
        offset_y = margin_top + max(0, (avail_h - draw_h) / 2.0)

        is_bw = (self.color_mode == "BW")

        # 1. Top & Left CAD Dimension Arrows
        painter.setPen(QPen(QColor("#000000"), 1.2))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        # Top Dimension (plate_length)
        dim_y = offset_y - 12
        painter.drawLine(int(offset_x), int(dim_y), int(offset_x + draw_w), int(dim_y))
        self._draw_arrow(painter, QPointF(offset_x, dim_y), QPointF(offset_x + 8, dim_y - 4), QPointF(offset_x + 8, dim_y + 4))
        self._draw_arrow(painter, QPointF(offset_x + draw_w, dim_y), QPointF(offset_x + draw_w - 8, dim_y - 4), QPointF(offset_x + draw_w - 8, dim_y + 4))
        painter.drawText(
            QRectF(offset_x, dim_y - 18, draw_w, 16),
            Qt.AlignmentFlag.AlignCenter,
            f"{plan.plate_length:.0f}"
        )

        # Left Dimension (plate_width)
        dim_x = offset_x - 12
        painter.drawLine(int(dim_x), int(offset_y), int(dim_x), int(offset_y + draw_h))
        self._draw_arrow(painter, QPointF(dim_x, offset_y), QPointF(dim_x - 4, offset_y + 8), QPointF(dim_x + 4, offset_y + 8))
        self._draw_arrow(painter, QPointF(dim_x, offset_y + draw_h), QPointF(dim_x - 4, offset_y + draw_h - 8), QPointF(dim_x + 4, offset_y + draw_h - 8))

        painter.save()
        painter.translate(dim_x - 8, offset_y + draw_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-draw_h / 2, -10, draw_h, 20), Qt.AlignmentFlag.AlignCenter, f"{plan.plate_width:.0f}")
        painter.restore()

        # 2. Draw Master Plate Background (Remnant / Scrap Hatch)
        plate_rect = QRectF(offset_x, offset_y, draw_w, draw_h)
        hatch_brush = QBrush(QColor("#000000"), Qt.BrushStyle.DiagCrossPattern)
        painter.setPen(QPen(QColor("#000000"), 1.2))
        painter.setBrush(hatch_brush)
        painter.drawRect(plate_rect)

        # 3. Draw Nested Parts
        cut_pen = QPen(QColor("#000000" if is_bw else "#16A34A"), 1.6)

        for idx, part in enumerate(plan.parts):
            px = offset_x + (part.y * scale)
            py = offset_y + (part.x * scale)
            pw = part.length * scale
            ph = part.width * scale

            part_rect = QRectF(px, py, pw, ph)

            if is_bw:
                part_fill = QColor("#FFFFFF")
            else:
                part_fill = PART_PASTEL_COLORS[idx % len(PART_PASTEL_COLORS)]

            painter.setBrush(QBrush(part_fill))
            painter.setPen(cut_pen)
            painter.drawRect(part_rect)

            # Draw labels and dimensions
            if pw >= 16 and ph >= 14:
                font_size = max(7, min(10, int(min(pw, ph) * 0.2)))
                painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
                painter.setPen(QPen(QColor("#000000")))

                if self.show_labels and part.part_mark:
                    painter.drawText(part_rect, Qt.AlignmentFlag.AlignCenter, part.part_mark)

                if self.show_sizes and pw > 30 and ph > 22:
                    dim_font = QFont("Segoe UI", max(6, font_size - 1))
                    painter.setFont(dim_font)

                    # Top edge: length
                    painter.drawText(
                        QRectF(px + 2, py + 2, pw - 4, 12),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                        f"{part.length:.0f}"
                    )

                    # Left edge: width
                    if ph > 35:
                        painter.save()
                        painter.translate(px + 10, py + ph / 2)
                        painter.rotate(-90)
                        painter.drawText(
                            QRectF(-ph / 2, -6, ph, 12),
                            Qt.AlignmentFlag.AlignCenter,
                            f"{part.width:.0f}"
                        )
                        painter.restore()

        # 4. Outer Boundary Frame
        painter.setPen(QPen(QColor("#000000"), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(plate_rect)

        # 5. Bottom Caption & Repetition Badge
        cap_y = offset_y + draw_h + 16
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#000000")))

        rep_count = getattr(plan, "repetition_count", 1)
        cut_len_str = f"Cut Dist= {plan.total_cut_length/1000.0:.2f} m;" if plan.total_cut_length > 0 else ""
        cap_text = f"Count= {rep_count} sheets;  Utilization= {plan.utilization_pct:.2f}%;  Scrap= {100.0 - plan.utilization_pct:.2f}%;  Parts= {plan.part_count} pcs;  {cut_len_str}"
        painter.drawText(QRectF(offset_x, cap_y, max(draw_w, 600.0), 24), Qt.AlignmentFlag.AlignLeft, cap_text)

    def _paint_1d_bar(self, painter: QPainter):
        plan = self.plan_1d
        if not plan or plan.stock_length <= 0:
            return

        w_widget = self.width()
        h_widget = self.height()

        margin_x = 50
        margin_y = 60

        avail_w = max(50, w_widget - 2 * margin_x)
        bar_len = plan.stock_length

        if self.fit_to_window:
            scale = avail_w / bar_len
        else:
            base_scale = avail_w / bar_len
            scale = base_scale * self.zoom_factor

        draw_w = bar_len * scale
        bar_h = 55.0

        offset_x = margin_x + max(0, (avail_w - draw_w) / 2.0)
        offset_y = (h_widget - bar_h) / 2.0

        is_bw = (self.color_mode == "BW")

        # Dimension line on top
        dim_y = offset_y - 12
        painter.setPen(QPen(QColor("#000000"), 1.2))
        painter.drawLine(int(offset_x), int(dim_y), int(offset_x + draw_w), int(dim_y))
        self._draw_arrow(painter, QPointF(offset_x, dim_y), QPointF(offset_x + 8, dim_y - 4), QPointF(offset_x + 8, dim_y + 4))
        self._draw_arrow(painter, QPointF(offset_x + draw_w, dim_y), QPointF(offset_x + draw_w - 8, dim_y - 4), QPointF(offset_x + draw_w - 8, dim_y + 4))

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(offset_x, dim_y - 18, draw_w, 16),
            Qt.AlignmentFlag.AlignCenter,
            f"{plan.designation} — {plan.stock_length:.0f} mm"
        )

        # Raw bar background with scrap cross-hatch
        bar_rect = QRectF(offset_x, offset_y, draw_w, bar_h)
        hatch_brush = QBrush(QColor("#000000"), Qt.BrushStyle.DiagCrossPattern)
        painter.setPen(QPen(QColor("#000000"), 1.2))
        painter.setBrush(hatch_brush)
        painter.drawRect(bar_rect)

        # Cuts
        cut_pen = QPen(QColor("#000000" if is_bw else "#16A34A"), 1.6)

        for idx, seg in enumerate(plan.segments):
            sx = offset_x + (seg.start_pos * scale)
            sw = seg.length * scale
            seg_rect = QRectF(sx, offset_y, sw, bar_h)

            fill_col = QColor("#FFFFFF") if is_bw else PART_PASTEL_COLORS[idx % len(PART_PASTEL_COLORS)]
            painter.setBrush(QBrush(fill_col))
            painter.setPen(cut_pen)
            painter.drawRect(seg_rect)

            if sw > 25:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QPen(QColor("#000000")))
                text = seg.part_mark
                if self.show_sizes:
                    text += f"\n{seg.length:.0f}"
                painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, text)

        # Boundary
        painter.setPen(QPen(QColor("#000000"), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bar_rect)

        # Bottom Caption
        cap_y = offset_y + bar_h + 16
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#000000")))
        rep_count = getattr(plan, "repetition_count", 1)
        cap_text = f"Count= {rep_count} bars;  Utilization= {plan.utilization_pct:.2f}%;  Scrap= {plan.waste_pct:.2f}%;  Cuts= {plan.part_count} pcs;  Remnant= {plan.raw_remnant_length:.0f} mm"
        painter.drawText(QRectF(offset_x, cap_y, max(draw_w, 600.0), 24), Qt.AlignmentFlag.AlignLeft, cap_text)

    def _draw_arrow(self, painter: QPainter, tip: QPointF, base1: QPointF, base2: QPointF):
        poly = QPolygonF([tip, base1, base2])
        painter.setBrush(QBrush(QColor("#000000")))
        painter.setPen(QPen(QColor("#000000"), 1.0))
        painter.drawPolygon(poly)
