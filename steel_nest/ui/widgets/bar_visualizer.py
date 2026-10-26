"""
High-Precision Scaled 1D Bar Visualization Widget
Renders stock bar, cut pieces, kerfs, trims, and remnants using QPainter.
"""
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPaintEvent
from PyQt6.QtCore import Qt, QRectF, QPointF

from steel_nest.models.nesting_plan import LinearBarPlan

# Palette of colors for nested parts
PART_COLORS = [
    QColor("#2563EB"), # Blue
    QColor("#059669"), # Emerald
    QColor("#D97706"), # Amber
    QColor("#7C3AED"), # Purple
    QColor("#0891B2"), # Cyan
    QColor("#DB2777"), # Pink
    QColor("#4F46E5"), # Indigo
    QColor("#EA580C"), # Orange
]

TRIM_COLOR = QColor("#64748B")     # Slate Gray
KERF_COLOR = QColor("#EF4444")     # Red
REUSABLE_COLOR = QColor("#10B981") # Green
WASTE_COLOR = QColor("#DC2626")    # Dark Red

class BarVisualizerWidget(QWidget):
    def __init__(self, plan: LinearBarPlan, min_remnant_mm: float = 500.0, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.min_remnant_mm = min_remnant_mm
        self.setMinimumHeight(125)
        self.setMouseTracking(True)
        self.hovered_segment = None

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Margins
        margin_x = 20
        bar_top = 40
        bar_height = 42
        avail_width = width - (2 * margin_x)

        if self.plan.stock_length <= 0 or avail_width <= 0:
            return

        scale = avail_width / self.plan.stock_length

        # 1. Header Information
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#F8FAFC")))
        header_text = f"Bar #{self.plan.bar_index} — {self.plan.stock_id} | {self.plan.designation} ({self.plan.grade}) | Stock: {self.plan.stock_length:.0f} mm"
        painter.drawText(margin_x, 24, header_text)

        # Utilization badge text
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        util_color = QColor("#10B981") if self.plan.utilization_pct >= 90 else (QColor("#F59E0B") if self.plan.utilization_pct >= 75 else QColor("#EF4444"))
        painter.setPen(QPen(util_color))
        badge_text = f"Util: {self.plan.utilization_pct:.1f}% | Parts: {self.plan.part_count} pcs"
        badge_rect = QRectF(width - 250, 8, 230, 20)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, badge_text)

        # 2. Draw Bar Background (Unused stock)
        bg_rect = QRectF(margin_x, bar_top, avail_width, bar_height)
        painter.setPen(QPen(QColor("#475569"), 1))
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.drawRoundedRect(bg_rect, 4, 4)

        # 3. Draw Start Trim
        curr_x = margin_x
        if self.plan.trim_start > 0:
            trim_w = self.plan.trim_start * scale
            trim_rect = QRectF(curr_x, bar_top, trim_w, bar_height)
            painter.setBrush(QBrush(TRIM_COLOR))
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawRect(trim_rect)
            curr_x += trim_w

        # 4. Draw Segments and Kerfs
        for idx, seg in enumerate(self.plan.segments):
            seg_w = seg.length * scale
            seg_rect = QRectF(curr_x, bar_top, seg_w, bar_height)
            color = PART_COLORS[idx % len(PART_COLORS)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#0F172A"), 1))
            painter.drawRect(seg_rect)

            # Label inside cut piece if wide enough
            if seg_w > 45:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QPen(QColor("#FFFFFF")))
                text_rect = QRectF(curr_x + 2, bar_top + 4, seg_w - 4, bar_height - 8)
                label = f"{seg.part_mark}\n{seg.length:.0f}"
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

            curr_x += seg_w

            # Kerf after segment
            if seg.kerf_after > 0:
                kerf_w = max(1.5, seg.kerf_after * scale)
                kerf_rect = QRectF(curr_x, bar_top, kerf_w, bar_height)
                painter.setBrush(QBrush(KERF_COLOR))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(kerf_rect)
                curr_x += kerf_w

        # 5. Draw End Trim if present
        if self.plan.trim_end > 0:
            # End trim is at the end of usable length or at the bar end
            end_trim_x = margin_x + avail_width - (self.plan.trim_end * scale)
            end_trim_w = self.plan.trim_end * scale
            painter.setBrush(QBrush(TRIM_COLOR))
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawRect(QRectF(end_trim_x, bar_top, end_trim_w, bar_height))

        # 6. Remnant section
        raw_rem = self.plan.raw_remnant_length
        if raw_rem > 0:
            is_reusable = raw_rem >= self.min_remnant_mm
            rem_color = REUSABLE_COLOR if is_reusable else WASTE_COLOR
            rem_w = raw_rem * scale
            rem_rect = QRectF(curr_x, bar_top, rem_w, bar_height)
            painter.setBrush(QBrush(rem_color))
            painter.setPen(QPen(QColor("#0F172A"), 1))
            painter.drawRect(rem_rect)

            if rem_w > 50:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QPen(QColor("#FFFFFF")))
                rem_text = f"{'REMNANT' if is_reusable else 'SCRAP'}\n{raw_rem:.0f} mm"
                painter.drawText(rem_rect, Qt.AlignmentFlag.AlignCenter, rem_text)

        # 7. Legend and stats below bar
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#94A3B8")))
        legend_y = bar_top + bar_height + 18
        
        stat_line = f"Used: {self.plan.used_length:.0f} mm | Parts: {self.plan.total_part_length:.0f} mm | Kerfs: {self.plan.total_kerf_length:.0f} mm | Trims: {self.plan.total_trim_length:.0f} mm | Remnant: {raw_rem:.0f} mm"
        painter.drawText(margin_x, legend_y, stat_line)

        painter.end()
