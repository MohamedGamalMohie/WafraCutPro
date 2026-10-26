"""
High-Precision 2D Steel Plate Layout Visualizer Widget
Renders plate boundary, safety margins, kerf spacing, positioned rectangular parts,
dimensions, rotation indicators, and offcuts using QPainter.
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPaintEvent
from PyQt6.QtCore import Qt, QRectF

from steel_nest.models.nesting_plan import PlateNestPlan

PLATE_COLORS = [
    QColor("#3B82F6"), # Blue
    QColor("#10B981"), # Green
    QColor("#F59E0B"), # Amber
    QColor("#8B5CF6"), # Purple
    QColor("#06B6D4"), # Cyan
    QColor("#EC4899"), # Pink
    QColor("#6366F1"), # Indigo
    QColor("#F97316"), # Orange
]

class PlateVisualizerWidget(QWidget):
    def __init__(self, plan: PlateNestPlan, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.setMinimumHeight(280)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w_widget = self.width()
        h_widget = self.height()

        margin_left = 30
        margin_top = 45
        padding = 20

        avail_w = w_widget - margin_left - padding
        avail_h = h_widget - margin_top - padding - 25

        if self.plan.plate_width <= 0 or self.plan.plate_length <= 0 or avail_w <= 0 or avail_h <= 0:
            return

        # Determine scale to fit plate in available widget area preserving aspect ratio
        scale_x = avail_w / self.plan.plate_length  # length along X
        scale_y = avail_h / self.plan.plate_width   # width along Y
        scale = min(scale_x, scale_y)

        draw_w = self.plan.plate_length * scale
        draw_h = self.plan.plate_width * scale

        # Title / Header
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#F8FAFC")))
        header = f"Plate #{self.plan.plate_index} — {self.plan.stock_id} | PL {self.plan.thickness_mm}mm ({self.plan.grade}) | Size: {self.plan.plate_width:.0f} x {self.plan.plate_length:.0f} mm"
        painter.drawText(margin_left, 24, header)

        # Util badge
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        util_color = QColor("#10B981") if self.plan.utilization_pct >= 80 else QColor("#F59E0B")
        painter.setPen(QPen(util_color))
        badge_text = f"Utilization: {self.plan.utilization_pct:.1f}% | Parts: {self.plan.part_count} pcs"
        painter.drawText(QRectF(w_widget - 260, 8, 240, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, badge_text)

        # Draw Plate Boundary (Raw steel plate)
        plate_rect = QRectF(margin_left, margin_top, draw_w, draw_h)
        painter.setPen(QPen(QColor("#475569"), 1.5))
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.drawRect(plate_rect)

        # Draw Edge Margin boundary (Dashed)
        margin_draw_w = self.plan.margin * scale
        margin_rect = QRectF(
            margin_left + margin_draw_w,
            margin_top + margin_draw_w,
            draw_w - 2 * margin_draw_w,
            draw_h - 2 * margin_draw_w
        )
        dashed_pen = QPen(QColor("#64748B"), 1, Qt.PenStyle.DashLine)
        painter.setPen(dashed_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(margin_rect)

        # Draw Placed Rectangular Parts
        for idx, part in enumerate(self.plan.parts):
            px = margin_left + (part.y * scale) # map along length
            py = margin_top + (part.x * scale)  # map along width
            pw = part.length * scale
            ph = part.width * scale

            part_rect = QRectF(px, py, pw, ph)
            color = PLATE_COLORS[idx % len(PLATE_COLORS)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#0F172A"), 1.2))
            painter.drawRect(part_rect)

            # Label inside part
            if pw > 35 and ph > 20:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QPen(QColor("#FFFFFF")))
                rot_flag = " ⟳" if part.rotated else ""
                label = f"{part.part_mark}{rot_flag}\n{part.width:.0f}x{part.length:.0f}"
                painter.drawText(part_rect, Qt.AlignmentFlag.AlignCenter, label)

        # Bottom info line
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#94A3B8")))
        info_y = margin_top + draw_h + 18
        tot_area = self.plan.total_plate_area_m2
        used_area = self.plan.used_parts_area_m2
        info_str = f"Total Area: {tot_area:.2f} m² | Parts Area: {used_area:.2f} m² | Unused Area: {tot_area - used_area:.2f} m² | Margin: {self.plan.margin:.0f} mm | Kerf: {self.plan.kerf:.0f} mm"
        painter.drawText(margin_left, int(info_y), info_str)

        painter.end()
