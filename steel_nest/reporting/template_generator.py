"""
Excel Template Generator for SteelNest Pro
Generates blank input templates with sample rows, comments, and instructions.
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
SAMPLE_FILL = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
WHITE_BOLD_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
REGULAR_FONT = Font(name="Segoe UI", size=10, color="000000")
MUTED_ITALIC = Font(name="Segoe UI", size=9, italic=True, color="595959")
THIN_BORDER_SIDE = Side(border_style="thin", color="D9D9D9")
GRID_BORDER = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)

class TemplateGenerator:
    @staticmethod
    def generate_unified_cut_list_template(file_path: str):
        """
        Generates a clean Excel template strictly matching the program interface:
        Sheet 1: قائمة القطع (Cut List) -> # | Length | Width | Quantity | Material | Rotation | Label
        Sheet 2: Stock (المخزن والخامات)  -> # | Length | Width | Quantity | Material | Label | Price
        Sheet 3: تعليمات (Instructions)   -> Guidance and column descriptions
        """
        wb = openpyxl.Workbook()
        
        # --- SHEET 1: PIECES ---
        ws_pieces = wb.active
        ws_pieces.title = "قائمة القطع (Cut List)"
        ws_pieces.views.sheetView[0].showGridLines = True

        ws_pieces["A1"] = "WafraCut Pro — نموذج إدخال القطع (Pieces Input Template)"
        ws_pieces["A1"].font = Font(name="Segoe UI", size=13, bold=True, color="1F4E79")
        ws_pieces["A2"] = "ملاحظة: للكمرات والمقاطع الطولية (1D) اجعل العرض Width = 0. لألواح وبليتات الصاج (2D) اكتب العرض. حدد Rotation بنعم (YES) أو لا (NO)."
        ws_pieces["A2"].font = MUTED_ITALIC

        headers_pieces = ["#", "Length", "Width", "Quantity", "Material", "Rotation", "Label"]
        for col_idx, text in enumerate(headers_pieces, start=1):
            cell = ws_pieces.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = GRID_BORDER

        sample_pieces = [
            (1, 5400.0, 0.0, 4, "IPE 300", "NO", "B-101"),
            (2, 6200.0, 0.0, 6, "IPE 300", "NO", "B-102"),
            (3, 4500.0, 0.0, 8, "HEA 200", "NO", "C-201"),
            (4, 200.0, 0.0, 520, "L60*6", "NO", "P-1"),
            (5, 600.0, 400.0, 8, "PL 12mm", "YES", "BP-1"),
            (6, 350.0, 250.0, 16, "PL 12mm", "YES", "GUS-1"),
            (7, 280.0, 150.0, 24, "PL 10mm", "YES", "STF-1"),
            (8, 600.0, 300.0, 4, "PL 16mm", "NO", "SPL-1"),
        ]

        for row_idx, data in enumerate(sample_pieces, start=5):
            is_plate = data[2] > 0
            row_fill = PatternFill(start_color="F5F3FF" if is_plate else "F2F5F9", fill_type="solid")
            for col_idx, val in enumerate(data, start=1):
                c = ws_pieces.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = row_fill
                c.border = GRID_BORDER
                if col_idx in (1, 4, 6):
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in (2, 3):
                    c.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws_pieces.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_pieces.column_dimensions[col_letter].width = max(max_len + 3, 15)
        ws_pieces.row_dimensions[4].height = 24

        # --- SHEET 2: STOCK ---
        ws_stock = wb.create_sheet(title="Stock (المخزن والخامات)")
        ws_stock.views.sheetView[0].showGridLines = True

        ws_stock["A1"] = "WafraCut Pro — نموذج إدخال المخزن (Stock Input Template)"
        ws_stock["A1"].font = Font(name="Segoe UI", size=13, bold=True, color="166534")
        ws_stock["A2"] = "ملاحظة: للأعواد والكمرات (1D) اجعل العرض Width = 0. لألواح الصاج (2D) اكتب أبعاد اللوح بالكامل."
        ws_stock["A2"].font = MUTED_ITALIC

        headers_stock = ["#", "Length", "Width", "Quantity", "Material", "Label", "Price"]
        stock_header_fill = PatternFill(start_color="166534", end_color="166534", fill_type="solid")
        for col_idx, text in enumerate(headers_stock, start=1):
            cell = ws_stock.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = stock_header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = GRID_BORDER

        sample_stock = [
            (1, 6000.0, 2000.0, 5, "PL 12mm", "STK-PL12", 0),
            (2, 6000.0, 2000.0, 5, "PL 10mm", "STK-PL10", 0),
            (3, 12000.0, 0.0, 10, "IPE 300", "STK-IPE300", 0),
            (4, 6000.0, 0.0, 20, "L60*6", "S235JR", 0),
        ]

        for row_idx, data in enumerate(sample_stock, start=5):
            row_fill = PatternFill(start_color="F0FDF4", fill_type="solid")
            for col_idx, val in enumerate(data, start=1):
                c = ws_stock.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = row_fill
                c.border = GRID_BORDER
                if col_idx in (1, 4):
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in (2, 3, 7):
                    c.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws_stock.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_stock.column_dimensions[col_letter].width = max(max_len + 3, 15)
        ws_stock.row_dimensions[4].height = 24

        # --- SHEET 3: INSTRUCTIONS ---
        ws_info = wb.create_sheet(title="تعليمات (Instructions)")
        ws_info.views.sheetView[0].showGridLines = True
        ws_info["A1"] = "دليل تعبئة شيت الإكسيل لبرنامج WafraCut Pro"
        ws_info["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="1F4E79")

        instructions = [
            ("1. الكمرات والقطاعات الخطية (1D)", "اكتب كود القطاع (مثل IPE 300 أو HEA 200 أو L 60x60x6) وضع الطول بالملم والعرض = 0."),
            ("2. ألواح وبليتات الصاج (2D)", "اكتب سمك البليت (مثل PL 12mm أو PL 20mm) وضع الطول والعرض بالملم."),
            ("3. السماح بالدوران (Rotation)", "اكتب YES إذا كان مسموحاً بتدوير البليت 90 درجة لتوفير الهالك، أو NO إذا كان الاتجاه ثابتاً (مثل اتجاه الدرفلة)."),
            ("4. الأبعاد والوحدات", "جميع الأطوال والعروض والسمك تُقاس بالمليمتر (mm)."),
            ("5. استيراد الملف", "من واجهة البرنامج الرئيسية اضغط على زر '📥 Import' لاختيار الملف وتحميل جميع القطع فوراً.")
        ]
        for idx, (title, desc) in enumerate(instructions, start=3):
            c1 = ws_info.cell(row=idx, column=1, value=title)
            c1.font = Font(name="Segoe UI", size=11, bold=True, color="1E293B")
            c2 = ws_info.cell(row=idx, column=2, value=desc)
            c2.font = REGULAR_FONT

        ws_info.column_dimensions["A"].width = 35
        ws_info.column_dimensions["B"].width = 85

        wb.save(file_path)

    @staticmethod
    def generate_linear_cut_list_template(file_path: str):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Linear Cut List Template"
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = "WAFRACUT PRO — LINEAR PARTS CUT LIST IMPORT TEMPLATE"
        ws["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="1F4E79")
        ws["A2"] = "Instructions: Fill in your required cut pieces below. Units must be millimeters (mm)."
        ws["A2"].font = MUTED_ITALIC

        headers = [
            "Part Mark*", "Section Designation*", "Steel Grade*", "Cut Length (mm)*",
            "Quantity*", "Weight per Piece (kg)", "Priority (1-5)", "Notes"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = GRID_BORDER

        sample_rows = [
            ("B-101", "IPE 300", "S355JR", 5400.0, 4, 227.8, 1, "Main roof girder"),
            ("B-102", "IPE 300", "S355JR", 6200.0, 6, 261.6, 1, "Secondary roof girder"),
            ("C-201", "HEA 200", "S355JR", 4500.0, 8, 190.3, 1, "Portal columns"),
            ("BR-1", "L 60x60x6", "S275JR", 2850.0, 12, 15.4, 2, "Wall bracing"),
            ("P-01", "CHS 114.3x5.0", "S355JR", 3100.0, 4, 41.8, 1, "Stair handrail posts")
        ]

        for row_idx, data in enumerate(sample_rows, start=5):
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = SAMPLE_FILL
                c.border = GRID_BORDER
                if col_idx in (1, 2, 3, 8):
                    c.alignment = Alignment(horizontal="left", vertical="center")
                elif col_idx in (5, 7):
                    c.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="right", vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

        wb.save(file_path)

    @staticmethod
    def generate_plate_cut_list_template(file_path: str):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Plate Cut List Template"
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = "WAFRACUT PRO — 2D STEEL PLATE CUT LIST IMPORT TEMPLATE"
        ws["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="1F4E79")
        ws["A2"] = "Instructions: Enter rectangular plate parts. Dimensions in millimeters (mm)."
        ws["A2"].font = MUTED_ITALIC

        headers = [
            "Part Mark*", "Thickness (mm)*", "Steel Grade*", "Width (mm)*",
            "Length (mm)*", "Quantity*", "Allow 90° Rotation (YES/NO)", "Notes"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = GRID_BORDER

        sample_rows = [
            ("BP-1", 20.0, "S355JR", 400.0, 450.0, 8, "YES", "Column base plates"),
            ("GUS-1", 12.0, "S275JR", 250.0, 350.0, 16, "YES", "Truss gussets"),
            ("STF-1", 10.0, "S275JR", 150.0, 280.0, 24, "YES", "Web stiffeners"),
            ("SPL-1", 16.0, "S355JR", 300.0, 600.0, 4, "NO", "Flange splice plates")
        ]

        for row_idx, data in enumerate(sample_rows, start=5):
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = SAMPLE_FILL
                c.border = GRID_BORDER
                c.alignment = Alignment(horizontal="left" if col_idx in (1, 3, 8) else ("center" if col_idx in (6, 7) else "right"), vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

        wb.save(file_path)

    @staticmethod
    def generate_stock_inventory_template(file_path: str):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stock Inventory Template"
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = "WAFRACUT PRO — STOCK INVENTORY IMPORT TEMPLATE"
        ws["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="1F4E79")
        ws["A2"] = "Instructions: Enter raw stock bars and plates in inventory. Dimensions in mm."
        ws["A2"].font = MUTED_ITALIC

        headers = [
            "Stock ID*", "Material Type (LINEAR/PLATE)*", "Section / Designation*",
            "Grade*", "Length (mm)*", "Width (mm)", "Thickness (mm)",
            "Available Qty*", "Unit Cost ($)", "Location", "Notes"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = GRID_BORDER

        sample_rows = [
            ("STK-IPE300-12M", "LINEAR", "IPE 300", "S355JR", 12000.0, 0, 0, 20, 520.0, "Bay 1", "Standard Mill Length"),
            ("STK-HEA200-12M", "LINEAR", "HEA 200", "S355JR", 12000.0, 0, 0, 15, 480.0, "Bay 1", "Standard Mill Length"),
            ("STK-L60-6M", "LINEAR", "L 60x60x6", "S275JR", 6000.0, 0, 0, 30, 65.0, "Bay 2", "Angles rack"),
            ("STK-PL20-2x6", "PLATE", "PL 20mm", "S355JR", 6000.0, 2000.0, 20.0, 5, 1250.0, "Plate Yard", "Mild Steel Plate")
        ]

        for row_idx, data in enumerate(sample_rows, start=5):
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = SAMPLE_FILL
                c.border = GRID_BORDER
                c.alignment = Alignment(horizontal="left" if col_idx in (1, 2, 3, 4, 10, 11) else ("center" if col_idx == 8 else "right"), vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

        wb.save(file_path)
