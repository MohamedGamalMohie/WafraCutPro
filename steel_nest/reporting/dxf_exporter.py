"""
DXF Exporter for SteelNest Pro
Generates standard AutoCAD ASCII DXF files (AC1009 / R12) for 2D plate nesting layouts.
"""
from pathlib import Path
from typing import List
from steel_nest.models.nesting_plan import PlateNestPlan, LinearBarPlan

class DXFExporter:
    @staticmethod
    def export_plate_nest_dxf(file_path: str, plan: PlateNestPlan):
        """
        Exports a 2D Plate nest layout to an AutoCAD compatible DXF file.
        Includes plate outer boundary, cutting contours, part marks, and dimensions.
        """
        lines = []
        # Header
        lines.extend([
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1009",
            "0", "ENDSEC",
        ])

        # Tables (Layers)
        lines.extend([
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LAYER",
            "70", "4",
            # Layer 0
            "0", "LAYER",
            "2", "0",
            "70", "0",
            "62", "7",
            "6", "CONTINUOUS",
            # Layer PLATE_BORDER (Color 1: Red)
            "0", "LAYER",
            "2", "PLATE_BORDER",
            "70", "0",
            "62", "1",
            "6", "CONTINUOUS",
            # Layer CUT_PARTS (Color 3: Green)
            "0", "LAYER",
            "2", "CUT_PARTS",
            "70", "0",
            "62", "3",
            "6", "CONTINUOUS",
            # Layer LABELS (Color 4: Cyan)
            "0", "LAYER",
            "2", "LABELS",
            "70", "0",
            "62", "4",
            "6", "CONTINUOUS",
            "0", "ENDTAB",
            "0", "ENDSEC",
        ])

        # Entities
        lines.extend([
            "0", "SECTION",
            "2", "ENTITIES",
        ])

        def add_rect(x1, y1, x2, y2, layer):
            # 4 lines
            for (xa, ya, xb, yb) in [
                (x1, y1, x2, y1),
                (x2, y1, x2, y2),
                (x2, y2, x1, y2),
                (x1, y2, x1, y1),
            ]:
                lines.extend([
                    "0", "LINE",
                    "8", layer,
                    "10", f"{xa:.3f}",
                    "20", f"{ya:.3f}",
                    "30", "0.0",
                    "11", f"{xb:.3f}",
                    "21", f"{yb:.3f}",
                    "31", "0.0",
                ])

        def add_text(x, y, text, height, layer):
            lines.extend([
                "0", "TEXT",
                "8", layer,
                "10", f"{x:.3f}",
                "20", f"{y:.3f}",
                "30", "0.0",
                "40", f"{height:.3f}",
                "1", str(text),
                "50", "0.0",
                "72", "1", # Center
                "11", f"{x:.3f}",
                "21", f"{y:.3f}",
                "31", "0.0",
            ])

        # Plate outer border
        add_rect(0.0, 0.0, plan.plate_length, plan.plate_width, "PLATE_BORDER")

        # Nested Parts
        for p in plan.parts:
            # part is placed at (p.y, p.x) with dimensions (p.length, p.width)
            x1 = p.y
            y1 = p.x
            x2 = p.y + p.length
            y2 = p.x + p.width
            add_rect(x1, y1, x2, y2, "CUT_PARTS")

            # Center text
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            txt_h = min(p.length, p.width) * 0.15
            txt_h = max(20.0, min(txt_h, 80.0))
            add_text(cx, cy + txt_h * 0.4, p.part_mark, txt_h, "LABELS")
            dim_str = f"{p.length:.0f}x{p.width:.0f}"
            add_text(cx, cy - txt_h * 0.6, dim_str, txt_h * 0.75, "LABELS")

        lines.extend([
            "0", "ENDSEC",
            "0", "EOF"
        ])

        with open(file_path, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(lines))

    @staticmethod
    def export_linear_dxf(file_path: str, plans: List[LinearBarPlan]):
        """
        Exports 1D Bar cutting plans to an AutoCAD DXF file showing laid out bars.
        """
        lines = [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", "AC1009",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES"
        ]

        def add_line(xa, ya, xb, yb, layer="0"):
            lines.extend([
                "0", "LINE",
                "8", layer,
                "10", f"{xa:.3f}",
                "20", f"{ya:.3f}",
                "30", "0.0",
                "11", f"{xb:.3f}",
                "21", f"{yb:.3f}",
                "31", "0.0",
            ])

        def add_rect(x1, y1, x2, y2, layer="0"):
            for (xa, ya, xb, yb) in [
                (x1, y1, x2, y1),
                (x2, y1, x2, y2),
                (x2, y2, x1, y2),
                (x1, y2, x1, y1),
            ]:
                add_line(xa, ya, xb, yb, layer)

        def add_text(x, y, text, height, layer="0"):
            lines.extend([
                "0", "TEXT",
                "8", layer,
                "10", f"{x:.3f}",
                "20", f"{y:.3f}",
                "30", "0.0",
                "40", f"{height:.3f}",
                "1", str(text),
            ])

        bar_height = 200.0
        gap_y = 350.0

        for b_idx, bar in enumerate(plans):
            y_base = b_idx * (bar_height + gap_y)
            # Bar title
            add_text(0.0, y_base + bar_height + 40.0, f"Bar #{bar.bar_index} - {bar.designation} ({bar.grade}) - Stock: {bar.stock_length:.0f}mm", 60.0)
            # Bar outer box
            add_rect(0.0, y_base, bar.stock_length, y_base + bar_height, "0")

            # Cut segments
            for seg in bar.segments:
                x1 = seg.start_pos
                x2 = seg.end_pos
                add_rect(x1, y_base, x2, y_base + bar_height, "1")
                # Label
                mid_x = (x1 + x2) / 2.0
                add_text(mid_x - 50.0, y_base + (bar_height / 2.0) - 15.0, f"{seg.part_mark} ({seg.length:.0f}mm)", 40.0)

        lines.extend([
            "0", "ENDSEC",
            "0", "EOF"
        ])

        with open(file_path, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(lines))
