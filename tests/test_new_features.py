import os
import tempfile
import openpyxl
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QMessageBox

from steel_nest.ui.main_window import MainWindow
from steel_nest.reporting.excel_exporter import ExcelReportExporter
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.core.plate_optimizer import PlateOptimizer
from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.models.project import Project

app = QApplication.instance() or QApplication([])

def test_cutting_optimization_pro_layout():
    with patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
        mw = MainWindow()
        view = mw.cutting_view
        # Check dual-pane splitter: Left (Inputs), Right (Results & Canvas)
        assert view.h_splitter.count() == 2
        # Check Left splitter: Top (Pieces), Bottom (Stock)
        assert view.v_splitter.count() == 2
        # Check Pieces table columns: #, Length, Width, Quantity, Material, Rotation, Label
        assert view.pieces_table.columnCount() == 7
        assert view.stock_table.columnCount() == 7
        # Check Start button exists and is labeled ▶ Start
        assert "Start" in view.btn_start.text()
        # Check Pattern tabs exist
        assert view.pattern_tabs is not None
        # Check Canvas exists
        assert view.canvas is not None

def test_dxf_export():
    from steel_nest.reporting.dxf_exporter import DXFExporter
    from steel_nest.models.nesting_plan import PlateNestPlan, PlacedPlatePart
    import tempfile

    plan = PlateNestPlan(
        plate_index=1,
        stock_id="STK-PL20",
        thickness_mm=20.0,
        grade="S355JR",
        plate_width=2000.0,
        plate_length=3000.0,
        margin=10.0,
        kerf=3.0,
        parts=[
            PlacedPlatePart(part_id="P1", part_mark="BP-1", x=0.0, y=0.0, width=500.0, length=600.0, rotated=False),
            PlacedPlatePart(part_id="P2", part_mark="GUS-1", x=500.0, y=0.0, width=400.0, length=700.0, rotated=False)
        ]
    )

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        dxf_path = tmp.name

    try:
        DXFExporter.export_plate_nest_dxf(dxf_path, plan)
        assert os.path.exists(dxf_path)
        with open(dxf_path, "r") as f:
            content = f.read()
        assert "SECTION" in content
        assert "ENTITIES" in content
        assert "BP-1" in content
        assert "GUS-1" in content
        assert "EOF" in content
    finally:
        if os.path.exists(dxf_path):
            os.remove(dxf_path)

def test_excel_workshop_bom_sheet():
    stock = [StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=5)]
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S355JR", length_mm=5400.0, quantity=2),
        PartCutItem(id="P2", mark="P2", designation="IPE 300", grade="S355JR", length_mm=6200.0, quantity=2)
    ]
    opt_1d = LinearOptimizer()
    res_1d = opt_1d.optimize(parts, stock)

    from steel_nest.models.stock import MaterialType
    plate_stock = [StockItem(id="PL-STK", designation="PL 12mm", grade="S275JR", length_mm=6000.0, width_mm=2000.0, thickness_mm=12.0, available_qty=2, material_type=MaterialType.PLATE)]
    plate_parts = [PlatePartItem(id="PL1", mark="BP-1", thickness_mm=12.0, grade="S275JR", width_mm=400.0, length_mm=600.0, quantity=4)]
    opt_2d = PlateOptimizer()
    res_2d = opt_2d.optimize(plate_parts, plate_stock)
    res_1d.plate_plans = res_2d.plate_plans

    proj = Project(id="PRJ-1", name="Building Steel", code="BLD-01")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tpath = tmp.name

    try:
        ExcelReportExporter.export_workshop_workbook(tpath, proj, res_1d)
        wb = openpyxl.load_workbook(tpath)
        assert "حصر الاستوك المطلوب (BOM)" in wb.sheetnames
        ws_bom = wb["حصر الاستوك المطلوب (BOM)"]
        
        # Check IPE 300 in BOM
        assert any(ws_bom.cell(row=r, column=2).value == "IPE 300" for r in range(6, 15))
        # Check PL 12mm in BOM
        assert any(ws_bom.cell(row=r, column=2).value == "PL 12mm" for r in range(10, 25))
    finally:
        if os.path.exists(tpath):
            os.remove(tpath)

def test_unified_template_and_importer():
    from steel_nest.reporting.template_generator import TemplateGenerator
    from steel_nest.reporting.excel_importer import ExcelDataImporter

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        template_path = tmp.name

    try:
        # 1. Generate template
        TemplateGenerator.generate_unified_cut_list_template(template_path)
        assert os.path.exists(template_path)

        # 2. Check workbook content
        wb = openpyxl.load_workbook(template_path)
        assert "قائمة القطع (Cut List)" in wb.sheetnames
        assert "تعليمات (Instructions)" in wb.sheetnames

        # 3. Import from this template
        parts_1d, parts_2d, errors = ExcelDataImporter.import_unified_cut_list(template_path)
        assert len(parts_1d) >= 4, f"Expected at least 4 linear parts, got {len(parts_1d)}"
        assert len(parts_2d) >= 4, f"Expected at least 4 plate parts, got {len(parts_2d)}"

        # Verify linear items have width 0 and correct length
        for p in parts_1d:
            assert p.length_mm > 0
            assert p.quantity > 0

        # Verify plate items have width > 0 and rotation flag
        for pl in parts_2d:
            assert pl.length_mm > 0
            assert pl.width_mm > 0
            assert pl.quantity > 0
            assert isinstance(pl.allow_rotation, bool)
    finally:
        if os.path.exists(template_path):
            os.remove(template_path)

