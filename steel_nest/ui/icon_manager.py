"""
Modern High-DPI Vector Icon Manager for SteelNest Pro
Renders crisp, resolution-independent vector icons for all application actions.
"""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF

class IconManager:
    _icon_cache = {}

    @classmethod
    def get_icon(cls, name: str, size: int = 24) -> QIcon:
        key = f"{name}_{size}"
        if key in cls._icon_cache:
            return cls._icon_cache[key]

        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(size)
        pad = s * 0.12
        r = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)

        if name == "start":
            # Green Triangle Play
            painter.setBrush(QBrush(QColor("#16A34A")))
            painter.setPen(QPen(QColor("#15803D"), 1.2))
            p1 = QPointF(r.left() + r.width() * 0.2, r.top())
            p2 = QPointF(r.right(), r.top() + r.height() * 0.5)
            p3 = QPointF(r.left() + r.width() * 0.2, r.bottom())
            painter.drawPolygon([p1, p2, p3])

        elif name == "accept":
            # Checkmark
            painter.setPen(QPen(QColor("#059669"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p1 = QPointF(r.left() + r.width() * 0.15, r.top() + r.height() * 0.5)
            p2 = QPointF(r.left() + r.width() * 0.45, r.bottom() - r.height() * 0.15)
            p3 = QPointF(r.right() - r.width() * 0.1, r.top() + r.height() * 0.2)
            painter.drawPolyline([p1, p2, p3])

        elif name == "tabular":
            # Data table grid
            painter.setPen(QPen(QColor("#2563EB"), 1.5))
            painter.setBrush(QBrush(QColor("#EFF6FF")))
            painter.drawRoundedRect(r, 2, 2)
            # horizontal & vertical line
            mid_y = r.top() + r.height() * 0.4
            mid_x = r.left() + r.width() * 0.5
            painter.drawLine(int(r.left()), int(mid_y), int(r.right()), int(mid_y))
            painter.drawLine(int(mid_x), int(mid_y), int(mid_x), int(r.bottom()))

        elif name == "sticker":
            # Adhesive Tag / Barcode label
            painter.setPen(QPen(QColor("#D97706"), 1.5))
            painter.setBrush(QBrush(QColor("#FEF3C7")))
            painter.drawRoundedRect(r, 3, 3)
            # barcode lines
            painter.setPen(QPen(QColor("#D97706"), 1.2))
            bx = r.left() + r.width() * 0.2
            bw = r.width() * 0.6
            by = r.top() + r.height() * 0.4
            bh = r.height() * 0.35
            for i in [0, 4, 7, 10, 14]:
                cur_x = bx + bw * (i / 15.0)
                painter.drawLine(int(cur_x), int(by), int(cur_x), int(by + bh))

        elif name == "excel":
            # Excel Sheet Green Badge
            painter.setPen(QPen(QColor("#15803D"), 1.2))
            painter.setBrush(QBrush(QColor("#16A34A")))
            painter.drawRoundedRect(r, 3, 3)
            painter.setFont(QFont("Segoe UI", int(s * 0.45), QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "X")

        elif name == "dxf":
            # AutoCAD drafting geometry
            painter.setPen(QPen(QColor("#EA580C"), 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r)
            painter.drawLine(int(r.left()), int(r.center().y()), int(r.right()), int(r.center().y()))
            painter.drawLine(int(r.center().x()), int(r.top()), int(r.center().x()), int(r.bottom()))

        elif name == "print":
            # Printer
            painter.setPen(QPen(QColor("#334155"), 1.5))
            painter.setBrush(QBrush(QColor("#F1F5F9")))
            body = QRectF(r.left(), r.top() + r.height() * 0.3, r.width(), r.height() * 0.5)
            painter.drawRoundedRect(body, 2, 2)
            # paper top
            paper = QRectF(r.left() + r.width() * 0.2, r.top(), r.width() * 0.6, r.height() * 0.4)
            painter.drawRect(paper)

        elif name == "multi_print":
            # Stack of pages (multi-layout)
            painter.setPen(QPen(QColor("#475569"), 1.4))
            p_back = QRectF(r.left() + 4, r.top(), r.width() - 4, r.height() - 4)
            painter.drawRect(p_back)
            p_front = QRectF(r.left(), r.top() + 4, r.width() - 4, r.height() - 4)
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.drawRect(p_front)
            # grid of 4
            mid_x = p_front.center().x()
            mid_y = p_front.center().y()
            painter.drawLine(int(p_front.left()), int(mid_y), int(p_front.right()), int(mid_y))
            painter.drawLine(int(mid_x), int(p_front.top()), int(mid_x), int(p_front.bottom()))

        elif name == "images":
            # Image Frame
            painter.setPen(QPen(QColor("#0891B2"), 1.5))
            painter.setBrush(QBrush(QColor("#ECFEFF")))
            painter.drawRoundedRect(r, 2, 2)
            # mountain peak
            p1 = QPointF(r.left() + 3, r.bottom() - 3)
            p2 = QPointF(r.center().x(), r.top() + r.height() * 0.4)
            p3 = QPointF(r.right() - 3, r.bottom() - 3)
            painter.setBrush(QBrush(QColor("#0891B2")))
            painter.drawPolygon([p1, p2, p3])

        elif name == "cnc":
            # CNC Code Document
            painter.setPen(QPen(QColor("#4F46E5"), 1.5))
            painter.setBrush(QBrush(QColor("#EEF2FF")))
            painter.drawRoundedRect(r, 2, 2)
            painter.setFont(QFont("Consolas", int(s * 0.35), QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#4F46E5")))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "G1")

        elif name == "products":
            # Complex Product / Cabinet box
            painter.setPen(QPen(QColor("#7C3AED"), 1.5))
            painter.setBrush(QBrush(QColor("#F5F3FF")))
            painter.drawRoundedRect(r, 2, 2)
            # shelf divider
            mid_y = r.center().y()
            painter.drawLine(int(r.left()), int(mid_y), int(r.right()), int(mid_y))

        elif name == "settings":
            # Gear
            painter.setPen(QPen(QColor("#475569"), 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(r.adjusted(3, 3, -3, -3))
            painter.drawEllipse(r.adjusted(6, 6, -6, -6))

        elif name == "paste":
            # Clipboard Paste
            painter.setPen(QPen(QColor("#0284C7"), 1.5))
            painter.setBrush(QBrush(QColor("#E0F2FE")))
            board = QRectF(r.left() + 2, r.top() + 3, r.width() - 4, r.height() - 3)
            painter.drawRoundedRect(board, 2, 2)
            clip = QRectF(r.center().x() - 4, r.top(), 8, 5)
            painter.drawRect(clip)

        elif name == "sort":
            # Up / Down Arrows
            painter.setPen(QPen(QColor("#334155"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # up arrow on left
            x_l = r.left() + r.width() * 0.3
            painter.drawLine(int(x_l), int(r.bottom() - 2), int(x_l), int(r.top() + 2))
            painter.drawLine(int(x_l), int(r.top() + 2), int(x_l - 3), int(r.top() + 6))
            # down arrow on right
            x_r = r.right() - r.width() * 0.3
            painter.drawLine(int(x_r), int(r.top() + 2), int(x_r), int(r.bottom() - 2))
            painter.drawLine(int(x_r), int(r.bottom() - 2), int(x_r + 3), int(r.bottom() - 6))

        elif name == "append":
            # Green Plus
            painter.setPen(QPen(QColor("#16A34A"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(r.center().x()), int(r.top() + 2), int(r.center().x()), int(r.bottom() - 2))
            painter.drawLine(int(r.left() + 2), int(r.center().y()), int(r.right() - 2), int(r.center().y()))

        elif name == "delete":
            # Red Cross
            painter.setPen(QPen(QColor("#DC2626"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(r.left() + 3), int(r.top() + 3), int(r.right() - 3), int(r.bottom() - 3))
            painter.drawLine(int(r.right() - 3), int(r.top() + 3), int(r.left() + 3), int(r.bottom() - 3))

        elif name == "clear":
            # Trash can
            painter.setPen(QPen(QColor("#64748B"), 1.5))
            body = QRectF(r.left() + 3, r.top() + 5, r.width() - 6, r.height() - 5)
            painter.drawRect(body)
            painter.drawLine(int(r.left()), int(r.top() + 4), int(r.right()), int(r.top() + 4))

        elif name == "save":
            # Floppy disk
            painter.setPen(QPen(QColor("#2563EB"), 1.5))
            painter.setBrush(QBrush(QColor("#EFF6FF")))
            painter.drawRoundedRect(r, 2, 2)
            disk_slider = QRectF(r.left() + 3, r.top(), r.width() - 6, r.height() * 0.4)
            painter.drawRect(disk_slider)

        else:
            # Fallback circle dot
            painter.setPen(QPen(QColor("#64748B"), 1.5))
            painter.drawEllipse(r)

        painter.end()

        icon = QIcon(pix)
        cls._icon_cache[key] = icon
        return icon
