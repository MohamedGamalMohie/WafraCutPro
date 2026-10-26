"""
Professional Streamlined Excel Export Engine for SteelNest Pro
Built using openpyxl with clean workshop styling, auto-filtering,
freeze panes, and zero pricing clutter.
"""
from typing import List, Dict, Any, Optional
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from steel_nest.models.nesting_plan import OptimizationResult, LinearBarPlan, PlateNestPlan
from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.project import Project

# Color Palette for Engineering Theme
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")     # Deep Steel Navy
SUBHEADER_FILL = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")  # Slate Navy
ZEBRA_FILL = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")      # Soft Ice Blue
ALERT_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")      # Soft Orange Warning
SUCCESS_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")    # Soft Green Success

# Cutting Optimization Pro Theme
CUTTING_PRO_HEADER_FILL = PatternFill(start_color="C6D9F1", end_color="C6D9F1", fill_type="solid") # Classic Soft Sky Blue
CUTTING_PRO_HEADER_FONT = Font(name="Segoe UI", size=10, bold=True, color="000000")
CUTTING_PRO_TITLE_FONT = Font(name="Segoe UI", size=11, bold=True, color="1F4E79")

WHITE_BOLD_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Segoe UI", size=15, bold=True, color="1F4E79")
SECTION_FONT = Font(name="Segoe UI", size=12, bold=True, color="1F4E79")
REGULAR_FONT = Font(name="Segoe UI", size=10, color="000000")
BOLD_FONT = Font(name="Segoe UI", size=10, bold=True, color="000000")
MUTED_FONT = Font(name="Segoe UI", size=9, italic=True, color="595959")

THIN_BORDER_SIDE = Side(border_style="thin", color="D9D9D9")
GRID_BORDER = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


class ExcelReportExporter:
    @staticmethod
    def export_workshop_workbook(file_path: str, project: Project, result: OptimizationResult, results_only: bool = False):
        """
        Creates a clean, production-focused workshop cutting plan:
        When results_only=True: exports ONLY Results (1D) and Results (2D) as requested by user.
        When results_only=False: includes Results + Summary + BOM + Cut Lists.
        """
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        if results_only:
            ws_res_1d = wb.create_sheet(title="Results (1D)")
            if result.linear_plans:
                ExcelReportExporter._build_sheet_results_1d_cutting_pro(ws_res_1d, project, result)
            else:
                ws_res_1d.append(["لا توجد نتائج تقطيع 1D في هذا المشروع (No 1D Linear Results)"])

            ws_res_2d = wb.create_sheet(title="Results (2D)")
            if result.plate_plans:
                ExcelReportExporter._build_sheet_results_2d_cutting_pro(ws_res_2d, project, result)
            else:
                ws_res_2d.append(["لا توجد نتائج تقطيع 2D في هذا المشروع (No 2D Plate Results)"])
        else:
            if result.linear_plans:
                ws_res_1d = wb.create_sheet(title="Results (1D)")
                ExcelReportExporter._build_sheet_results_1d_cutting_pro(ws_res_1d, project, result)

            if result.plate_plans:
                ws_res_2d = wb.create_sheet(title="Results (2D)")
                ExcelReportExporter._build_sheet_results_2d_cutting_pro(ws_res_2d, project, result)

        if not results_only:
            ws1 = wb.create_sheet(title="ملخص التقطيع (Summary)")
            ExcelReportExporter._build_sheet1_summary(ws1, project, result)

            ws_bom = wb.create_sheet(title="حصر الاستوك المطلوب (BOM)")
            ExcelReportExporter._build_sheet_stock_requirements(ws_bom, project, result)

            if result.linear_plans:
                ws2 = wb.create_sheet(title="أعواد الكمرات (1D Cutting)")
                ExcelReportExporter._build_sheet2_cutting_plan(ws2, project, result)

            ws3 = wb.create_sheet(title="جدول القطع (Cut List)")
            ExcelReportExporter._build_sheet3_workshop_cutlist(ws3, result)

            if result.plate_plans:
                ws4 = wb.create_sheet(title="ألواح الصاج (2D Plates)")
                ExcelReportExporter._build_sheet7_plate_nesting(ws4, result)

        if not wb.sheetnames:
            ws_default = wb.create_sheet(title="Results")
            ws_default.views.sheetView[0].showGridLines = True
            ws_default["A1"] = "No cutting results available."

        wb.save(file_path)

    @staticmethod
    def export_full_workbook(
        file_path: str,
        project: Project,
        result: OptimizationResult,
        parts_1d: List[PartCutItem],
        parts_2d: List[PlatePartItem],
        stock_items: List[StockItem],
        remnants: List[RemnantItem]
    ):
        """Full archival export including Results (1D/2D) and full breakdown sheets."""
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        if result.linear_plans:
            ws_res_1d = wb.create_sheet(title="Results (1D)")
            ExcelReportExporter._build_sheet_results_1d_cutting_pro(ws_res_1d, project, result)

        if result.plate_plans:
            ws_res_2d = wb.create_sheet(title="Results (2D)")
            ExcelReportExporter._build_sheet_results_2d_cutting_pro(ws_res_2d, project, result)

        ws1 = wb.create_sheet(title="Executive Summary")
        ExcelReportExporter._build_sheet1_summary(ws1, project, result)

        ws2 = wb.create_sheet(title="Detailed Cutting Plan")
        ExcelReportExporter._build_sheet2_cutting_plan(ws2, project, result)

        ws3 = wb.create_sheet(title="Cut List")
        ExcelReportExporter._build_sheet3_cut_list(ws3, result, parts_1d, parts_2d)

        ws4 = wb.create_sheet(title="Stock Purchase List")
        ExcelReportExporter._build_sheet4_stock_purchase(ws4, result, stock_items)

        ws5 = wb.create_sheet(title="Remnants and Offcuts")
        ExcelReportExporter._build_sheet5_remnants(ws5, result, remnants)

        ws6 = wb.create_sheet(title="Material Summary")
        ExcelReportExporter._build_sheet6_material_summary(ws6, result)

        ws7 = wb.create_sheet(title="Plate Nesting")
        ExcelReportExporter._build_sheet7_plate_nesting(ws7, result)

        ws8 = wb.create_sheet(title="Unprocessed Exceptions")
        ExcelReportExporter._build_sheet8_exceptions(ws8, result)

        wb.save(file_path)

    # ----------------------------------------------------
    # SHEET 1: EXECUTIVE SUMMARY
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet1_summary(ws, project: Project, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True

        ws["B2"] = "WAFRACUT PRO — خطة التقطيع والاستغلال الفني"
        ws["B2"].font = TITLE_FONT
        ws["B3"] = f"مشروع: {project.name} | كود: {project.code} | تاريخ الإصدار: {res.created_at}"
        ws["B3"].font = MUTED_FONT

        # Metadata Table
        ws["B5"] = "بيانات التشغيل والتحسين (Run Metadata)"
        ws["B5"].font = SECTION_FONT

        meta = [
            ("اسم المشروع (Project)", project.name),
            ("كود المشروع (Code)", project.code),
            ("طريقة التقطيع (Mode)", res.mode),
            ("حالة المحرك (Solver Status)", f"{res.solver_status} ({'حل مثالي مؤكد' if res.is_proven_optimal else 'أفضل حل عملي'})"),
            ("زمن الحساب (Execution Time)", f"{res.execution_time_sec:.2f} ثانية")
        ]

        for idx, (label, val) in enumerate(meta, start=6):
            ws.cell(row=idx, column=2, value=label).font = BOLD_FONT
            ws.cell(row=idx, column=2).fill = ZEBRA_FILL
            ws.cell(row=idx, column=2).border = GRID_BORDER
            ws.cell(row=idx, column=3, value=val).font = REGULAR_FONT
            ws.cell(row=idx, column=3).border = GRID_BORDER

        # KPI Metrics Table
        ws["B13"] = "مؤشرات الإنتاج والاستغلال الفني (Key Metrics)"
        ws["B13"].font = SECTION_FONT

        kpis = [
            ("إجمالي القطع المطلوبة (Total Required)", f"{res.total_parts_required} قطعة"),
            ("إجمالي القطع الموزعة (Nested Parts)", f"{res.total_parts_nested} قطعة"),
            ("أعواد / ألواح الاستوك المستهلكة (Stock Used)", f"{res.total_stock_used} وحدة"),
            ("إجمالي أطوال الاستوك المستهلك (Material Consumed)", f"{res.total_material_length_m:.2f} م"),
            ("إجمالي أطوال القطع الصافية (Net Parts Length)", f"{res.total_parts_length_m:.2f} م"),
            ("إجمالي الفضلات القابلة للاستخدام (Reusable Remnants)", f"{res.total_reusable_remnants_length_m:.2f} م"),
            ("إجمالي الهالك غير الصالح (Scrap Waste)", f"{res.total_unusable_waste_length_m:.2f} م"),
            ("نسبة استغلال الخامة (Overall Utilization)", f"{res.overall_utilization_pct:.1f} %"),
            ("نسبة الهالك الكلي (Waste Percentage)", f"{res.overall_waste_pct:.1f} %")
        ]

        for idx, (label, val) in enumerate(kpis, start=14):
            ws.cell(row=idx, column=2, value=label).font = BOLD_FONT
            ws.cell(row=idx, column=2).fill = ZEBRA_FILL
            ws.cell(row=idx, column=2).border = GRID_BORDER

            c_val = ws.cell(row=idx, column=3, value=val)
            c_val.font = BOLD_FONT if "Utilization" in label else REGULAR_FONT
            c_val.border = GRID_BORDER
            if "Utilization" in label:
                c_val.fill = SUCCESS_FILL
            elif "Waste" in label and res.overall_waste_pct > 25.0:
                c_val.fill = ALERT_FILL

        ws.column_dimensions["B"].width = 38
        ws.column_dimensions["C"].width = 46

    # ----------------------------------------------------
    # SHEET: FINAL STOCK REQUIREMENTS (RAW STOCK BOM)
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet_stock_requirements(ws, project: Project, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A6"

        ws["A2"] = "حصر الاستوك النهائي المطلوب للتصنيع والشراء (Required Raw Stock BOM)"
        ws["A2"].font = TITLE_FONT
        ws["A3"] = f"مشروع: {project.name} | كود: {project.code} | تاريخ الإصدار: {res.created_at}"
        ws["A3"].font = MUTED_FONT

        # 1. 1D Beams & Linear Profiles Requirements
        ws["A5"] = "أولاً: حصر أعواد الكمرات والمقاطع الطولية المطلوبة (1D Beams & Profiles)"
        ws["A5"].font = SECTION_FONT

        headers_1d = [
            "م", "القطاع (Section)", "الرتبة (Grade)", "طول العود المطلوب (mm)",
            "العدد المطلوب (Bars Qty)", "إجمالي الأطوال (Total m)", "عدد القطع المنتجة",
            "الفضلات المتبقية (m)", "نسبة الاستغلال %", "ملاحظة التشغيل"
        ]

        for col_idx, text in enumerate(headers_1d, start=1):
            cell = ws.cell(row=6, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 7
        total_bars = 0
        total_len_m = 0.0
        total_parts = 0

        # Group linear plans by (designation, grade, stock_length)
        groups_1d = {}
        for plan in res.linear_plans:
            key = (plan.designation, plan.grade, plan.stock_length)
            if key not in groups_1d:
                groups_1d[key] = {
                    "count": 0, "parts": 0, "used_len": 0.0, "rem_len": 0.0, "utils": []
                }
            groups_1d[key]["count"] += 1
            groups_1d[key]["parts"] += plan.part_count
            groups_1d[key]["used_len"] += plan.used_length
            groups_1d[key]["rem_len"] += plan.raw_remnant_length
            groups_1d[key]["utils"].append(plan.utilization_pct)

        item_num = 1
        for (desig, grd, stk_len), data in groups_1d.items():
            qty = data["count"]
            tot_m = (stk_len * qty) / 1000.0
            avg_util = sum(data["utils"]) / len(data["utils"]) if data["utils"] else 0.0
            rem_m = data["rem_len"] / 1000.0

            total_bars += qty
            total_len_m += tot_m
            total_parts += data["parts"]

            row_data = [
                item_num,
                desig,
                grd,
                f"{stk_len:.0f} mm",
                f"{qty} عود",
                round(tot_m, 2),
                f"{data['parts']} قطعة",
                round(rem_m, 2),
                round(avg_util, 1),
                "جاهز للصرف والتقطيع"
            ]

            fill = ZEBRA_FILL if item_num % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(row_data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 4, 5, 7, 9, 10) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)

            row_idx += 1
            item_num += 1

        # Totals row for 1D
        if groups_1d:
            ws.cell(row=row_idx, column=1, value="الإجمالي").font = BOLD_FONT
            ws.cell(row=row_idx, column=1).alignment = ALIGN_CENTER
            ws.cell(row=row_idx, column=5, value=f"{total_bars} عود").font = BOLD_FONT
            ws.cell(row=row_idx, column=5).alignment = ALIGN_CENTER
            ws.cell(row=row_idx, column=6, value=round(total_len_m, 2)).font = BOLD_FONT
            ws.cell(row=row_idx, column=6).alignment = ALIGN_RIGHT
            ws.cell(row=row_idx, column=7, value=f"{total_parts} قطعة").font = BOLD_FONT
            ws.cell(row=row_idx, column=7).alignment = ALIGN_CENTER
            for c in range(1, 11):
                ws.cell(row=row_idx, column=c).border = GRID_BORDER
                ws.cell(row=row_idx, column=c).fill = SUCCESS_FILL
            row_idx += 2
        else:
            ws.cell(row=row_idx, column=1, value="لا توجد مقاطع كمـرات في هذا المشروع").font = MUTED_FONT
            row_idx += 2

        # 2. 2D Plates Requirements (if any)
        if res.plate_plans:
            ws.cell(row=row_idx, column=1, value="ثانياً: حصر ألواح الصاج المطلوبة (2D Steel Plates)").font = SECTION_FONT
            row_idx += 1

            headers_2d = [
                "م", "الخامة / السمك", "الرتبة (Grade)", "أبعاد اللوح المطلوب (mm)",
                "عدد الألواح المطلوبة", "إجمالي المساحة (m²)", "عدد القطع المنتجة",
                "نسبة الاستغلال %", "ملاحظة التشغيل"
            ]

            for col_idx, text in enumerate(headers_2d, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=text)
                cell.font = WHITE_BOLD_FONT
                cell.fill = SUBHEADER_FILL
                cell.alignment = ALIGN_CENTER
                cell.border = GRID_BORDER

            row_idx += 1
            groups_2d = {}
            for pl in res.plate_plans:
                key = (pl.thickness_mm, pl.grade, pl.plate_width, pl.plate_length)
                if key not in groups_2d:
                    groups_2d[key] = {
                        "count": 0, "parts": 0, "area": 0.0, "utils": []
                    }
                groups_2d[key]["count"] += 1
                groups_2d[key]["parts"] += pl.part_count
                groups_2d[key]["area"] += pl.total_plate_area_m2
                groups_2d[key]["utils"].append(pl.utilization_pct)

            tot_plates = 0
            tot_pl_area = 0.0
            tot_pl_parts = 0
            p_num = 1

            for (thk, grd, pw, pl_len), data in groups_2d.items():
                qty = data["count"]
                tot_plates += qty
                tot_pl_area += data["area"]
                tot_pl_parts += data["parts"]
                avg_util = sum(data["utils"]) / len(data["utils"]) if data["utils"] else 0.0

                p_row_data = [
                    p_num,
                    f"PL {thk:.0f}mm",
                    grd,
                    f"{pw:.0f} × {pl_len:.0f} mm",
                    f"{qty} لوح",
                    round(data["area"], 2),
                    f"{data['parts']} قطعة",
                    round(avg_util, 1),
                    "جاهز للصرف والقص"
                ]

                fill = ZEBRA_FILL if p_num % 2 == 0 else PatternFill(fill_type=None)
                for col_idx, val in enumerate(p_row_data, start=1):
                    c = ws.cell(row=row_idx, column=col_idx, value=val)
                    c.font = REGULAR_FONT
                    c.fill = fill
                    c.border = GRID_BORDER
                    c.alignment = ALIGN_CENTER if col_idx in (1, 4, 5, 7, 8, 9) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)

                row_idx += 1
                p_num += 1

            # Total row for 2D
            ws.cell(row=row_idx, column=1, value="الإجمالي").font = BOLD_FONT
            ws.cell(row=row_idx, column=1).alignment = ALIGN_CENTER
            ws.cell(row=row_idx, column=5, value=f"{tot_plates} لوح").font = BOLD_FONT
            ws.cell(row=row_idx, column=5).alignment = ALIGN_CENTER
            ws.cell(row=row_idx, column=6, value=round(tot_pl_area, 2)).font = BOLD_FONT
            ws.cell(row=row_idx, column=6).alignment = ALIGN_RIGHT
            ws.cell(row=row_idx, column=7, value=f"{tot_pl_parts} قطعة").font = BOLD_FONT
            ws.cell(row=row_idx, column=7).alignment = ALIGN_CENTER
            for c in range(1, 10):
                ws.cell(row=row_idx, column=c).border = GRID_BORDER
                ws.cell(row=row_idx, column=c).fill = SUCCESS_FILL

        # Adjust columns width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # ----------------------------------------------------
    # SHEET 2: DETAILED CUTTING PLAN
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet2_cutting_plan(ws, project: Project, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "خطة تفصيل أعواد الكمرات والمقاطع الطولية (1D Cutting Plan)"
        ws["A2"].font = TITLE_FONT

        headers = [
            "رقم العود (Bar #)", "كود الاستوك (Stock ID)", "القطاع (Section)", "الرتبة (Grade)",
            "طول العود (Length mm)", "عدد القطع", "توزيعة القطع والأطوال (Sequence mm)",
            "طول القطع (mm)", "سماكة المنشار (Kerf)", "تهذيب الأطراف (Trim)", "المستخدم (Used mm)",
            "الفضلة المتبقية (Remnant mm)", "نسبة الاستغلال %", "حالة الفضلة (Remnant Class)"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        min_rem = project.settings.min_remnant_length_mm if project and project.settings else 500.0

        for plan in res.linear_plans:
            seq_text = " + ".join([f"{seg.part_mark} ({seg.length:.0f})" for seg in plan.segments])
            rem = plan.raw_remnant_length
            is_reusable = rem >= min_rem
            rem_class = "فضلة صالحة للاستخدام" if is_reusable else "هالك غير مستغل"

            data = [
                plan.bar_index,
                plan.stock_id,
                plan.designation,
                plan.grade,
                plan.stock_length,
                plan.part_count,
                seq_text,
                plan.total_part_length,
                plan.total_kerf_length,
                plan.total_trim_length,
                plan.used_length,
                round(rem, 1),
                round(plan.utilization_pct, 1),
                rem_class
            ]

            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 6, 14) else (ALIGN_LEFT if col_idx in (2, 3, 4, 7) else ALIGN_RIGHT)

            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:N{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 13), 50)

    # ----------------------------------------------------
    # SHEET 3: WORKSHOP CUT LIST
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet3_workshop_cutlist(ws, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "قائمة القطع المطلوبة للتصنيع (Workshop Cut List)"
        ws["A2"].font = TITLE_FONT

        headers = [
            "كود القطعة (Mark)", "القطاع / الخامة (Section)", "الرتبة (Grade)",
            "الطول (Length mm)", "العود / اللوح المخصص (Assigned Unit)", "حالة التنفيذ (Status)"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = SUBHEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        # 1D Pieces
        for plan in res.linear_plans:
            for seg in plan.segments:
                data = [
                    seg.part_mark, plan.designation, plan.grade,
                    round(seg.length, 1), f"عود #{plan.bar_index} ({plan.stock_id})", "جاهز للتقطيع ✔"
                ]
                fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
                for col_idx, val in enumerate(data, start=1):
                    c = ws.cell(row=row_idx, column=col_idx, value=val)
                    c.font = REGULAR_FONT
                    c.fill = fill
                    c.border = GRID_BORDER
                    c.alignment = ALIGN_CENTER if col_idx in (1, 5, 6) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
                row_idx += 1

        # 2D Pieces
        for pl in res.plate_plans:
            for p in pl.parts:
                data = [
                    p.part_mark, f"PL {pl.thickness_mm}mm", pl.grade,
                    f"{p.width:.0f}x{p.length:.0f}", f"لوح #{pl.plate_index} ({pl.stock_id})", "جاهز للتقطيع ✔"
                ]
                fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
                for col_idx, val in enumerate(data, start=1):
                    c = ws.cell(row=row_idx, column=col_idx, value=val)
                    c.font = REGULAR_FONT
                    c.fill = fill
                    c.border = GRID_BORDER
                    c.alignment = ALIGN_CENTER if col_idx in (1, 5, 6) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
                row_idx += 1

        # Unassigned
        for un in res.unassigned_parts:
            data = [
                un.part_mark, un.designation, un.grade,
                str(un.length_or_dims), "غير متاح استوك", f"مرفوض: {un.reason}"
            ]
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = ALERT_FILL
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 5, 6) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:F{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # ----------------------------------------------------
    # SHEET 3 (LEGACY): CUT LIST WITH TOTALS
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet3_cut_list(ws, res: OptimizationResult, parts_1d: List[PartCutItem], parts_2d: List[PlatePartItem]):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "CUT LIST — REQUIRED VS NESTED FABRICATION PARTS"
        ws["A2"].font = TITLE_FONT

        headers = [
            "Part Mark", "Designation", "Grade", "Length (mm)", "Width (mm)",
            "Required Qty", "Nested Qty", "Status"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = SUBHEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        for p in parts_1d:
            status = "Fully Nested"
            data = [p.mark, p.designation, p.grade, p.length_mm, "-", p.quantity, p.quantity, status]
            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 5, 8) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
            row_idx += 1

        for p2 in parts_2d:
            status = "Fully Nested"
            data = [p2.mark, f"PL {p2.thickness_mm}mm", p2.grade, p2.length_mm, p2.width_mm, p2.quantity, p2.quantity, status]
            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 8) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:H{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 40)

    # ----------------------------------------------------
    # SHEET 4: STOCK PURCHASE / CONSUMPTION LIST (NO COSTS)
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet4_stock_purchase(ws, res: OptimizationResult, stock_items: List[StockItem]):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "RAW STOCK INVENTORY & CONSUMPTION REPORT"
        ws["A2"].font = TITLE_FONT

        headers = [
            "Stock ID", "Designation", "Grade", "Length (mm)", "Width (mm)",
            "Consumed Units", "Available In Inventory", "Procurement Status"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        consumed_map = {}
        for p in res.linear_plans:
            consumed_map[p.stock_id] = consumed_map.get(p.stock_id, 0) + 1
        for pl in res.plate_plans:
            consumed_map[pl.stock_id] = consumed_map.get(pl.stock_id, 0) + 1

        row_idx = 5
        for s in stock_items:
            used = consumed_map.get(s.id, 0)
            avail = s.available_qty
            status = "Sufficient" if avail >= used else "Shortage"

            data = [
                s.id, s.designation, s.grade, s.length_mm,
                s.width_mm if s.width_mm > 0 else "-", used, avail, status
            ]
            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 5, 8) else (ALIGN_LEFT if col_idx in (2, 3) else ALIGN_RIGHT)
            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:H{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 35)

    # ----------------------------------------------------
    # SHEET 5: REMNANTS AND OFFCUTS
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet5_remnants(ws, res: OptimizationResult, remnants: List[RemnantItem]):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "REUSABLE REMNANTS & OFFCUTS INVENTORY"
        ws["A2"].font = TITLE_FONT

        headers = [
            "Remnant ID", "Parent Stock ID", "Section", "Grade",
            "Offcut Length (mm)", "Offcut Width (mm)", "Origin Bar Index", "Status"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = SUBHEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        if not remnants:
            # Extract from linear plans if remnants list is empty
            for plan in res.linear_plans:
                if plan.raw_remnant_length >= 500.0:
                    data = [
                        f"REM-{plan.stock_id}-{plan.bar_index}", plan.stock_id, plan.designation,
                        plan.grade, round(plan.raw_remnant_length, 1), "-", plan.bar_index, "Reusable"
                    ]
                    fill = SUCCESS_FILL
                    for col_idx, val in enumerate(data, start=1):
                        c = ws.cell(row=row_idx, column=col_idx, value=val)
                        c.font = REGULAR_FONT
                        c.fill = fill
                        c.border = GRID_BORDER
                        c.alignment = ALIGN_CENTER if col_idx in (1, 6, 7, 8) else ALIGN_LEFT
                    row_idx += 1
        else:
            for rem in remnants:
                data = [
                    rem.id, rem.parent_stock_id, rem.designation, rem.grade,
                    rem.length_mm, rem.width_mm if rem.width_mm > 0 else "-", "-", rem.status
                ]
                fill = SUCCESS_FILL
                for col_idx, val in enumerate(data, start=1):
                    c = ws.cell(row=row_idx, column=col_idx, value=val)
                    c.font = REGULAR_FONT
                    c.fill = fill
                    c.border = GRID_BORDER
                    c.alignment = ALIGN_CENTER if col_idx in (1, 6, 8) else ALIGN_LEFT
                row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:H{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 35)

    # ----------------------------------------------------
    # SHEET 6: MATERIAL SUMMARY
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet6_material_summary(ws, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "MATERIAL GROUPED UTILIZATION SUMMARY"
        ws["A2"].font = TITLE_FONT

        headers = [
            "Designation", "Grade", "Bars / Units Used", "Stock Length (m)",
            "Parts Length (m)", "Remnants (m)", "Waste (m)", "Utilization %"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        groups = {}
        for p in res.linear_plans:
            key = (p.designation, p.grade)
            if key not in groups:
                groups[key] = {"count": 0, "stock_m": 0.0, "parts_m": 0.0, "rem_m": 0.0, "waste_m": 0.0}
            groups[key]["count"] += 1
            groups[key]["stock_m"] += p.stock_length / 1000.0
            groups[key]["parts_m"] += p.total_part_length / 1000.0
            groups[key]["rem_m"] += p.raw_remnant_length / 1000.0
            groups[key]["waste_m"] += (p.total_trim_length + p.total_kerf_length) / 1000.0

        row_idx = 5
        for (desig, grd), stats in groups.items():
            tot_stk = stats["stock_m"]
            util = (stats["parts_m"] / tot_stk * 100.0) if tot_stk > 0 else 0.0
            data = [
                desig, grd, stats["count"], round(tot_stk, 2),
                round(stats["parts_m"], 2), round(stats["rem_m"], 2),
                round(stats["waste_m"], 2), round(util, 1)
            ]
            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (3, 8) else (ALIGN_LEFT if col_idx in (1, 2) else ALIGN_RIGHT)
            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:H{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 30)

    # ----------------------------------------------------
    # SHEET 7: PLATE NESTING (NO COSTS)
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet7_plate_nesting(ws, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "تفصيل وتوزيع ألواح الصاج (2D Plate Nesting)"
        ws["A2"].font = TITLE_FONT

        headers = [
            "رقم اللوح (Plate #)", "كود الاستوك (Stock ID)", "السمك (mm)", "الرتبة (Grade)",
            "أبعاد اللوح (Dimensions mm)", "عدد القطع", "القطع الموزعة (Placed Parts)",
            "المساحة المستغلة (m²)", "إجمالي مساحة اللوح (m²)", "نسبة الاستغلال %", "المساحة المتبقية (m²)"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = HEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        for plan in res.plate_plans:
            tot_a = plan.total_plate_area_m2
            used_a = plan.used_parts_area_m2
            waste_a = max(0.0, tot_a - used_a)
            parts_summary = ", ".join([f"{p.part_mark} ({p.width:.0f}x{p.length:.0f})" for p in plan.parts])

            data = [
                plan.plate_index, plan.stock_id, plan.thickness_mm, plan.grade,
                f"{plan.plate_width:.0f} x {plan.plate_length:.0f}",
                plan.part_count, parts_summary, round(used_a, 3), round(tot_a, 3),
                round(plan.utilization_pct, 1), round(waste_a, 3)
            ]
            fill = ZEBRA_FILL if row_idx % 2 == 0 else PatternFill(fill_type=None)
            for col_idx, val in enumerate(data, start=1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.fill = fill
                c.border = GRID_BORDER
                c.alignment = ALIGN_CENTER if col_idx in (1, 6) else (ALIGN_LEFT if col_idx in (2, 4, 5, 7) else ALIGN_RIGHT)
            row_idx += 1

        if row_idx > 5:
            ws.auto_filter.ref = f"A4:K{row_idx - 1}"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # ----------------------------------------------------
    # SHEET 8: UNPROCESSED OR EXCEPTION PARTS
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet8_exceptions(ws, res: OptimizationResult):
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A5"

        ws["A2"] = "UNPROCESSED & INFEASIBLE EXCEPTION PARTS"
        ws["A2"].font = TITLE_FONT

        headers = [
            "Part Mark", "Designation", "Grade", "Length / Dimensions",
            "Quantity", "Reason For Exception / Infeasibility"
        ]

        for col_idx, text in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = WHITE_BOLD_FONT
            cell.fill = SUBHEADER_FILL
            cell.alignment = ALIGN_CENTER
            cell.border = GRID_BORDER

        row_idx = 5
        if not res.unassigned_parts:
            ws.cell(row=5, column=1, value="None. All parts were successfully nested within stock boundaries.").font = REGULAR_FONT
        else:
            for part in res.unassigned_parts:
                data = [
                    part.part_mark, part.designation, part.grade,
                    part.length_or_dims, part.quantity, part.reason
                ]
                for col_idx, val in enumerate(data, start=1):
                    c = ws.cell(row=row_idx, column=col_idx, value=val)
                    c.font = REGULAR_FONT
                    c.fill = ALERT_FILL
                    c.border = GRID_BORDER
                    c.alignment = ALIGN_LEFT if col_idx != 5 else ALIGN_RIGHT
                row_idx += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 60)

    # ----------------------------------------------------
    # CUTTING OPTIMIZATION PRO REPLICA: RESULTS (1D)
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet_results_1d_cutting_pro(ws, project: Project, res: OptimizationResult):
        """Generates exact multi-section Cutting Optimization Pro report matching user's CSV."""
        ws.views.sheetView[0].showGridLines = True
        curr_row = 1

        # Section 1: Results (1D)
        ws.cell(row=curr_row, column=1, value="Results (1D)").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_1 = ["#", "Length", "Material", "Quantity", "Label", "Waste", "Waste %", "Price", "Pieces"]
        for c, h in enumerate(headers_1, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        for idx, plan in enumerate(res.linear_plans, start=1):
            counts = defaultdict(int)
            segs = getattr(plan, 'segments', getattr(plan, 'cuts', []))
            for seg in segs:
                l_val = getattr(seg, 'length', getattr(seg, 'cut_length', 0.0))
                counts[l_val] += 1
            pieces_str = " + ".join([f"{count}x{int(l) if float(l).is_integer() else l}" for l, count in sorted(counts.items(), reverse=True)])
            if not pieces_str:
                pieces_str = "-"

            mat_name = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or getattr(plan, 'stock_material', None) or "Steel"
            rem_len = getattr(plan, 'raw_remnant_length', getattr(plan, 'waste_length', 0.0))
            reps = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))

            row_vals = [
                idx,
                int(plan.stock_length) if float(plan.stock_length).is_integer() else plan.stock_length,
                mat_name,
                reps,
                plan.stock_id or project.code or "S235JR",
                int(rem_len) if float(rem_len).is_integer() else round(rem_len, 1),
                round(plan.waste_pct, 2),
                0,
                pieces_str
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (3, 5, 9) else ALIGN_CENTER
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 2: Utilized parts
        ws.cell(row=curr_row, column=1, value="Utilized parts").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_2 = ["#", "Length", "Quantity", "Material", "Label", "Customer name"]
        for c, h in enumerate(headers_2, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        part_agg = defaultdict(lambda: {"qty": 0, "material": "", "label": ""})
        for plan in res.linear_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat_name = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or getattr(plan, 'stock_material', "Steel")
            segs = getattr(plan, 'segments', getattr(plan, 'cuts', []))
            for seg in segs:
                l_val = getattr(seg, 'length', getattr(seg, 'cut_length', 0.0))
                mark = getattr(seg, 'part_mark', getattr(seg, 'part_id', ""))
                part_agg[l_val]["qty"] += rep
                part_agg[l_val]["material"] = mat_name
                part_agg[l_val]["label"] = mark

        p_idx = 1
        for l, data in sorted(part_agg.items(), key=lambda x: -x[0]):
            row_vals = [
                p_idx,
                int(l) if float(l).is_integer() else l,
                data["qty"],
                data["material"],
                data["label"],
                project.name or ""
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (4, 5, 6) else ALIGN_CENTER
            p_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 3: Utilized bars
        ws.cell(row=curr_row, column=1, value="Utilized bars").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_3 = ["Length", "Quantity", "Material", "Label", "Price"]
        for c, h in enumerate(headers_3, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        bars_agg = defaultdict(int)
        bars_mat = {}
        for plan in res.linear_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            k = plan.stock_length
            bars_agg[k] += rep
            bars_mat[k] = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or "Steel"

        for l, count in sorted(bars_agg.items(), key=lambda x: -x[0]):
            row_vals = [
                int(l) if float(l).is_integer() else l,
                count,
                bars_mat.get(l, "Steel"),
                project.code or "S235JR",
                0
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (3, 4) else ALIGN_CENTER
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 4: Disposed waste
        ws.cell(row=curr_row, column=1, value="Disposed waste").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_4 = ["#", "Length", "Material", "Quantity"]
        for c, h in enumerate(headers_4, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        min_usable = 800.0  # default reusable threshold
        disposed_agg = defaultdict(int)
        for plan in res.linear_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            rem_len = getattr(plan, 'raw_remnant_length', getattr(plan, 'waste_length', 0.0))
            mat_name = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or "Steel"
            if 0 < rem_len < min_usable:
                disposed_agg[(rem_len, mat_name)] += rep

        d_idx = 1
        for (w_len, mat), count in sorted(disposed_agg.items()):
            row_vals = [d_idx, int(w_len) if float(w_len).is_integer() else round(w_len, 1), mat, count]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 3 else ALIGN_CENTER
            d_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 5: Reused waste
        ws.cell(row=curr_row, column=1, value="Reused waste").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_5 = ["#", "Length", "Material", "Quantity"]
        for c, h in enumerate(headers_5, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        reused_agg = defaultdict(int)
        for plan in res.linear_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            rem_len = getattr(plan, 'raw_remnant_length', getattr(plan, 'waste_length', 0.0))
            mat_name = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or "Steel"
            if rem_len >= min_usable:
                reused_agg[(rem_len, mat_name)] += rep

        r_idx = 1
        for (w_len, mat), count in sorted(reused_agg.items(), reverse=True):
            row_vals = [r_idx, int(w_len) if float(w_len).is_integer() else round(w_len, 1), mat, count]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 3 else ALIGN_CENTER
            r_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 6: Materials
        ws.cell(row=curr_row, column=1, value="Materials").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_6 = ["#", "Material", "Total used length", "Total used length %", "Reused waste", "Disposed waste", "Size of used bars", "Price (PIECES)", "Price (Stock)"]
        for c, h in enumerate(headers_6, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        mat_stats = defaultdict(lambda: {"used_len": 0.0, "total_stock": 0.0, "reused": 0.0, "disposed": 0.0})
        for plan in res.linear_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat = getattr(plan, 'designation', None) or getattr(plan, 'grade', None) or "Steel"
            segs = getattr(plan, 'segments', getattr(plan, 'cuts', []))
            parts_len = sum(getattr(s, 'length', getattr(s, 'cut_length', 0.0)) for s in segs) * rep
            stock_len = plan.stock_length * rep
            rem_len = getattr(plan, 'raw_remnant_length', getattr(plan, 'waste_length', 0.0))
            waste = rem_len * rep
            mat_stats[mat]["used_len"] += parts_len
            mat_stats[mat]["total_stock"] += stock_len
            if rem_len >= min_usable:
                mat_stats[mat]["reused"] += waste
            else:
                mat_stats[mat]["disposed"] += waste

        m_idx = 1
        for mat, st in mat_stats.items():
            tot_stock = st["total_stock"] or 1.0
            used_pct = round((st["used_len"] / tot_stock) * 100.0, 3)
            row_vals = [
                m_idx,
                mat,
                int(st["used_len"]),
                used_pct,
                int(st["reused"]),
                int(st["disposed"]),
                int(st["total_stock"]),
                0,
                0
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 2 else ALIGN_CENTER
            m_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 7: Other statistics
        ws.cell(row=curr_row, column=1, value="Other statistics").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        ws.cell(row=curr_row, column=1, value="Parameter").font = CUTTING_PRO_HEADER_FONT
        ws.cell(row=curr_row, column=1).fill = CUTTING_PRO_HEADER_FILL
        ws.cell(row=curr_row, column=1).border = GRID_BORDER
        ws.cell(row=curr_row, column=2, value="Value").font = CUTTING_PRO_HEADER_FONT
        ws.cell(row=curr_row, column=2).fill = CUTTING_PRO_HEADER_FILL
        ws.cell(row=curr_row, column=2).border = GRID_BORDER
        curr_row += 1

        tot_used_len = sum(st["used_len"] for st in mat_stats.values())
        tot_stock_len = sum(st["total_stock"] for st in mat_stats.values()) or 1.0
        tot_reused = sum(st["reused"] for st in mat_stats.values())
        tot_disposed = sum(st["disposed"] for st in mat_stats.values())
        tot_cuts_count = sum(len(getattr(p, 'segments', getattr(p, 'cuts', []))) * getattr(p, 'repetition_count', getattr(p, 'repetitions', 1)) for p in res.linear_plans)

        stats_rows = [
            ("Total used length", f"{int(tot_used_len)}"),
            ("Number of pieces", f"{tot_cuts_count}"),
            ("Size of used bars", f"{int(tot_stock_len)}"),
            ("Reused waste", f"{int(tot_reused)}"),
            ("Reused waste %", f"{round((tot_reused / tot_stock_len) * 100.0, 1)}"),
            ("Disposed waste", f"{int(tot_disposed)}"),
            ("Disposed waste %", f"{round((tot_disposed / tot_stock_len) * 100.0, 1)}"),
            ("Utilized parts (Price)", "0"),
            ("Bars (Price)", "0"),
            ("Running time", f"{res.execution_time_sec:.3f}s")
        ]

        for param, val in stats_rows:
            c1 = ws.cell(row=curr_row, column=1, value=param)
            c1.font = BOLD_FONT
            c1.border = GRID_BORDER
            c2 = ws.cell(row=curr_row, column=2, value=val)
            c2.font = REGULAR_FONT
            c2.border = GRID_BORDER
            c2.alignment = ALIGN_CENTER
            curr_row += 1

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    # ----------------------------------------------------
    # CUTTING OPTIMIZATION PRO REPLICA: RESULTS (2D)
    # ----------------------------------------------------
    @staticmethod
    def _build_sheet_results_2d_cutting_pro(ws, project: Project, res: OptimizationResult):
        """Generates exact multi-section 2D Cutting Optimization Pro report."""
        ws.views.sheetView[0].showGridLines = True
        curr_row = 1

        # Section 1: Results (2D)
        ws.cell(row=curr_row, column=1, value="Results (2D)").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_1 = ["#", "Length", "Width", "Material", "Quantity", "Label", "Waste", "Waste %", "Price", "Pieces"]
        for c, h in enumerate(headers_1, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        for idx, plan in enumerate(res.plate_plans, start=1):
            counts = defaultdict(int)
            pts = getattr(plan, 'parts', getattr(plan, 'placed_parts', []))
            for pt in pts:
                counts[(pt.width, pt.length)] += 1
            pieces_str = " + ".join([
                f"{count}x({int(w) if float(w).is_integer() else w}x{int(l) if float(l).is_integer() else l})"
                for (w, l), count in sorted(counts.items(), reverse=True)
            ])
            if not pieces_str:
                pieces_str = "-"

            mat_name = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
            reps = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))

            row_vals = [
                idx,
                int(plan.plate_length) if float(plan.plate_length).is_integer() else plan.plate_length,
                int(plan.plate_width) if float(plan.plate_width).is_integer() else plan.plate_width,
                mat_name,
                reps,
                plan.stock_id or project.code or "Sheet",
                int(plan.waste_area) if float(plan.waste_area).is_integer() else round(plan.waste_area, 1),
                round(100.0 - plan.utilization_pct, 2),
                0,
                pieces_str
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (4, 6, 10) else ALIGN_CENTER
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 2: Utilized parts
        ws.cell(row=curr_row, column=1, value="Utilized parts").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_2 = ["#", "Length", "Width", "Quantity", "Material", "Texture", "Label", "Customer name"]
        for c, h in enumerate(headers_2, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        parts_2d_agg = defaultdict(lambda: {"qty": 0, "material": "", "label": ""})
        for plan in res.plate_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat_name = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
            pts = getattr(plan, 'parts', getattr(plan, 'placed_parts', []))
            for pt in pts:
                k = (pt.length, pt.width)
                parts_2d_agg[k]["qty"] += rep
                parts_2d_agg[k]["material"] = mat_name
                parts_2d_agg[k]["label"] = getattr(pt, 'part_mark', getattr(pt, 'part_id', ""))

        p_idx = 1
        for (l, w), data in sorted(parts_2d_agg.items(), key=lambda x: -(x[0][0]*x[0][1])):
            row_vals = [
                p_idx,
                int(l) if float(l).is_integer() else l,
                int(w) if float(w).is_integer() else w,
                data["qty"],
                data["material"],
                "None",
                data["label"],
                project.name or ""
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (5, 7, 8) else ALIGN_CENTER
            p_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 3: Utilized sheets
        ws.cell(row=curr_row, column=1, value="Utilized sheets").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_3 = ["Length", "Width", "Quantity", "Material", "Label", "Price"]
        for c, h in enumerate(headers_3, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        sheets_agg = defaultdict(int)
        sheets_mat = {}
        for plan in res.plate_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            k = (plan.plate_length, plan.plate_width)
            sheets_agg[k] += rep
            sheets_mat[k] = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")

        for (l, w), count in sorted(sheets_agg.items(), key=lambda x: -(x[0][0]*x[0][1])):
            row_vals = [
                int(l) if float(l).is_integer() else l,
                int(w) if float(w).is_integer() else w,
                count,
                sheets_mat.get((l, w), "Steel"),
                project.code or "Sheet",
                0
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c in (4, 5) else ALIGN_CENTER
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 4: Disposed waste
        ws.cell(row=curr_row, column=1, value="Disposed waste").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_4 = ["#", "Length", "Width", "Material", "Quantity"]
        for c, h in enumerate(headers_4, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        min_usable_area = 500.0 * 500.0  # 0.25 m2
        disposed_2d = defaultdict(int)
        for plan in res.plate_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat_name = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
            if 0 < plan.waste_area < min_usable_area:
                disposed_2d[(plan.waste_area, mat_name)] += rep

        d_idx = 1
        for (w_area, mat), count in sorted(disposed_2d.items()):
            row_vals = [d_idx, int(w_area**0.5), int(w_area**0.5), mat, count]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 4 else ALIGN_CENTER
            d_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 5: Reused waste
        ws.cell(row=curr_row, column=1, value="Reused waste").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_5 = ["#", "Length", "Width", "Material", "Quantity"]
        for c, h in enumerate(headers_5, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        reused_2d = defaultdict(int)
        for plan in res.plate_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat_name = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
            if plan.waste_area >= min_usable_area:
                reused_2d[(plan.waste_area, mat_name)] += rep

        r_idx = 1
        for (w_area, mat), count in sorted(reused_2d.items(), reverse=True):
            row_vals = [r_idx, int(w_area**0.5), int(w_area**0.5), mat, count]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 4 else ALIGN_CENTER
            r_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 6: Materials
        ws.cell(row=curr_row, column=1, value="Materials").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        headers_6 = ["#", "Material", "Total used area", "Total used area %", "Reused waste", "Disposed waste", "Size of used sheets", "Price (PIECES)", "Price (Stock)"]
        for c, h in enumerate(headers_6, start=1):
            cell = ws.cell(row=curr_row, column=c, value=h)
            cell.font = CUTTING_PRO_HEADER_FONT
            cell.fill = CUTTING_PRO_HEADER_FILL
            cell.border = GRID_BORDER
            cell.alignment = ALIGN_CENTER
        curr_row += 1

        mat_2d_stats = defaultdict(lambda: {"used_area": 0.0, "total_sheet_area": 0.0, "reused": 0.0, "disposed": 0.0})
        for plan in res.plate_plans:
            rep = getattr(plan, 'repetition_count', getattr(plan, 'repetitions', 1))
            mat = getattr(plan, 'grade', None) or getattr(plan, 'material_grade', "Steel")
            pts = getattr(plan, 'parts', getattr(plan, 'placed_parts', []))
            u_area = sum(pt.width * pt.length for pt in pts) * rep
            sheet_area = (plan.plate_width * plan.plate_length) * rep
            w_area = plan.waste_area * rep
            mat_2d_stats[mat]["used_area"] += u_area
            mat_2d_stats[mat]["total_sheet_area"] += sheet_area
            if plan.waste_area >= min_usable_area:
                mat_2d_stats[mat]["reused"] += w_area
            else:
                mat_2d_stats[mat]["disposed"] += w_area

        m_idx = 1
        for mat, st in mat_2d_stats.items():
            tot_st = st["total_sheet_area"] or 1.0
            used_pct = round((st["used_area"] / tot_st) * 100.0, 3)
            row_vals = [
                m_idx,
                mat,
                int(st["used_area"]),
                used_pct,
                int(st["reused"]),
                int(st["disposed"]),
                int(st["total_sheet_area"]),
                0,
                0
            ]
            for c, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c, value=val)
                cell.font = REGULAR_FONT
                cell.border = GRID_BORDER
                cell.alignment = ALIGN_LEFT if c == 2 else ALIGN_CENTER
            m_idx += 1
            curr_row += 1

        curr_row += 1  # Empty row

        # Section 7: Other statistics
        ws.cell(row=curr_row, column=1, value="Other statistics").font = CUTTING_PRO_TITLE_FONT
        curr_row += 1

        ws.cell(row=curr_row, column=1, value="Parameter").font = CUTTING_PRO_HEADER_FONT
        ws.cell(row=curr_row, column=1).fill = CUTTING_PRO_HEADER_FILL
        ws.cell(row=curr_row, column=1).border = GRID_BORDER
        ws.cell(row=curr_row, column=2, value="Value").font = CUTTING_PRO_HEADER_FONT
        ws.cell(row=curr_row, column=2).fill = CUTTING_PRO_HEADER_FILL
        ws.cell(row=curr_row, column=2).border = GRID_BORDER
        curr_row += 1

        tot_used_area = sum(st["used_area"] for st in mat_2d_stats.values())
        tot_sheet_area = sum(st["total_sheet_area"] for st in mat_2d_stats.values()) or 1.0
        tot_reused_2d = sum(st["reused"] for st in mat_2d_stats.values())
        tot_disposed_2d = sum(st["disposed"] for st in mat_2d_stats.values())
        tot_parts_2d_count = sum(len(getattr(p, 'parts', getattr(p, 'placed_parts', []))) * getattr(p, 'repetition_count', getattr(p, 'repetitions', 1)) for p in res.plate_plans)

        stats_2d_rows = [
            ("Total used area", f"{int(tot_used_area)}"),
            ("Number of pieces", f"{tot_parts_2d_count}"),
            ("Size of used sheets", f"{int(tot_sheet_area)}"),
            ("Reused waste", f"{int(tot_reused_2d)}"),
            ("Reused waste %", f"{round((tot_reused_2d / tot_sheet_area) * 100.0, 1)}"),
            ("Disposed waste", f"{int(tot_disposed_2d)}"),
            ("Disposed waste %", f"{round((tot_disposed_2d / tot_sheet_area) * 100.0, 1)}"),
            ("Utilized parts (Price)", "0"),
            ("Sheets (Price)", "0"),
            ("Running time", f"{res.execution_time_sec:.3f}s")
        ]

        for param, val in stats_2d_rows:
            c1 = ws.cell(row=curr_row, column=1, value=param)
            c1.font = BOLD_FONT
            c1.border = GRID_BORDER
            c2 = ws.cell(row=curr_row, column=2, value=val)
            c2.font = REGULAR_FONT
            c2.border = GRID_BORDER
            c2.alignment = ALIGN_CENTER
            curr_row += 1

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)
