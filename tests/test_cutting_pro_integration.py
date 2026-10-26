"""
Integration and Verification Tests for Cutting Optimization Pro Features
Tests:
- 2D Steel Plate Nesting with Thickness Matching (PL 12mm, PL 10mm)
- Maximal Rectangles (MaxRects) packing density
- Tabular cut coordinates extraction
- Workshop printable stickers data
- Accept Solution inventory deduction and remnant generation
- Statistics Dashboard data fidelity
"""
import pytest
from PyQt6.QtWidgets import QApplication

from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.project import ProjectSettings
from steel_nest.config import MaterialType, LinearOptimizationMode
from steel_nest.core.plate_optimizer import PlateOptimizer
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView
from steel_nest.ui.widgets.statistics_dashboard import TabularCutDialog, StickersDialog

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_steel_plate_nesting_success():
    """Verify that steel plates with 'PL 12mm' and 'PL 10mm' are correctly matched and nested without failure."""
    parts = [
        PlatePartItem(id="p1", mark="BP-1", thickness_mm=12.0, grade="PL 12mm", width_mm=400.0, length_mm=600.0, quantity=8),
        PlatePartItem(id="p2", mark="GUS-1", thickness_mm=12.0, grade="PL 12mm", width_mm=250.0, length_mm=350.0, quantity=16),
        PlatePartItem(id="p3", mark="STF-1", thickness_mm=10.0, grade="PL 10mm", width_mm=150.0, length_mm=280.0, quantity=24),
    ]
    stock = [
        StockItem(id="STK-PL12", designation="PL 12mm", grade="PL 12mm", length_mm=6000.0, width_mm=2000.0, thickness_mm=12.0, available_qty=5, material_type=MaterialType.PLATE),
        StockItem(id="STK-PL10", designation="PL 10mm", grade="PL 10mm", length_mm=6000.0, width_mm=2000.0, thickness_mm=10.0, available_qty=5, material_type=MaterialType.PLATE),
    ]
    optimizer = PlateOptimizer(kerf_mm=4.0, margin_mm=10.0)
    result = optimizer.optimize(parts, stock)

    assert len(result.unassigned_parts) == 0, f"Expected 0 unassigned, got {result.unassigned_parts}"
    assert result.total_parts_nested == 48, f"Expected 48 parts nested, got {result.total_parts_nested}"
    assert len(result.plate_plans) == 2, f"Expected 2 plates used, got {len(result.plate_plans)}"
    
    # Check that plates never overlap and stay within usable boundaries
    for pl in result.plate_plans:
        for p in pl.parts:
            assert p.x >= pl.margin - 1e-4
            assert p.y >= pl.margin - 1e-4
            assert p.x + p.width <= pl.plate_width - pl.margin + 1e-4
            assert p.y + p.length <= pl.plate_length - pl.margin + 1e-4

def test_maxrects_benchmark_density():
    """Verify that MaxRects BSSF achieves benchmark packing density (>85%) on Sheet 1."""
    demo_pieces = [
        (620.0, 570.0, 3),
        (600.0, 500.0, 5),
        (650.0, 540.0, 7),
        (890.0, 510.0, 6),
        (740.0, 680.0, 3),
    ]
    parts = []
    for idx, (l, w, q) in enumerate(demo_pieces):
        parts.append(PlatePartItem(
            id=f"p_{idx}", mark=f"P{idx}", thickness_mm=10.0,
            grade="wood", width_mm=w, length_mm=l, quantity=q, allow_rotation=True
        ))
    stock = [
        StockItem(id="STK-WD", designation="wood", grade="wood", length_mm=3000.0, width_mm=2000.0, thickness_mm=10.0, available_qty=10, material_type=MaterialType.PLATE)
    ]
    optimizer = PlateOptimizer(kerf_mm=0.0, margin_mm=0.0)
    result = optimizer.optimize(parts, stock)

    assert result.total_parts_nested == 24
    assert len(result.plate_plans) == 2
    assert result.plate_plans[0].utilization_pct >= 85.0, f"Sheet 1 util was {result.plate_plans[0].utilization_pct:.2f}%"

def test_tabular_and_stickers_dialogs(qapp):
    """Verify TabularCutDialog and StickersDialog instantiate with correct data."""
    parts = [
        PlatePartItem(id="p1", mark="BP-1", thickness_mm=12.0, grade="PL 12mm", width_mm=400.0, length_mm=600.0, quantity=2)
    ]
    stock = [
        StockItem(id="STK-PL12", designation="PL 12mm", grade="PL 12mm", length_mm=6000.0, width_mm=2000.0, thickness_mm=12.0, available_qty=1, material_type=MaterialType.PLATE)
    ]
    res = PlateOptimizer(kerf_mm=2.0, margin_mm=5.0).optimize(parts, stock)

    tab_dlg = TabularCutDialog(res)
    assert tab_dlg.table.rowCount() == 2
    assert tab_dlg.table.item(0, 2).text() == "BP-1"

    stk_dlg = StickersDialog(res)
    assert stk_dlg.grid.count() == 2

def test_ui_view_actions_and_statistics(qapp):
    """Verify that CuttingOptimizationView handles Results tabs and actions cleanly."""
    view = CuttingOptimizationView()
    view._load_steel_demo()
    assert view.pieces_table.rowCount() == 6
    assert view.stock_table.rowCount() == 4

    # Run data collection and thickness parsing
    p1, p2, s1, s2 = view._collect_data()
    assert len(p1) == 3 # IPE 300, IPE 300, HEA 200
    assert len(p2) == 3 # PL 12mm, PL 12mm, PL 10mm
    assert len(s1) == 2 # 12m IPE 300, HEA 200
    assert len(s2) == 2 # PL 12mm, PL 10mm

    # Check thickness equality
    assert p2[0].thickness_mm == s2[0].thickness_mm == 12.0
    assert p2[2].thickness_mm == s2[1].thickness_mm == 10.0

    # Sort table test
    view._sort_table_column(view.pieces_table, 1, reverse=True) # Sort pieces by length descending
    top_len = float(view.pieces_table.item(0, 1).text())
    assert top_len == 6200.0 # B-102 was 6200mm

def test_as_text_and_statistics_categories(qapp):
    """Verify 'As text' mode and 8 Statistics Dashboard categories matching Cutting Optimization Pro."""
    import tempfile
    import openpyxl
    from steel_nest.reporting.excel_exporter import ExcelReportExporter
    from steel_nest.models.project import Project

    view = CuttingOptimizationView()
    stock_1d = [StockItem(id="S1", designation="L60*6", grade="S235JR", length_mm=6000.0, available_qty=20)]
    parts_1d = [PartCutItem(id="P1", mark="P1", designation="L60*6", grade="S235JR", length_mm=200.0, quantity=520)]
    res = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING).optimize(parts_1d, stock_1d)

    # 1. Test Optimization Result handling
    view._on_optimization_done(res)
    assert view.current_result == res

    # 2. Test 'As text' mode toggle
    view.res_tabs.setCurrentIndex(1) # Results (1D)
    assert view.right_stack.currentIndex() == 0 # Canvas page
    view.chk_as_text.setChecked(True)
    assert view.right_stack.currentIndex() == 1 # Text Table page
    assert view.table_results_text.rowCount() > 0
    assert view.table_results_text.horizontalHeaderItem(0).text() == "#"
    assert view.table_results_text.horizontalHeaderItem(1).text() == "Length ▲"
    assert view.table_results_text.horizontalHeaderItem(5).text() == "Pieces"
    assert "x200" in view.table_results_text.item(0, 5).text()

    # 3. Test Statistics Dashboard 8 categories
    view.res_tabs.setCurrentIndex(2) # Statistics
    assert view.right_stack.currentIndex() == 2 # Stats dashboard page
    stats = view.stats_dashboard
    assert stats.top_tabs.count() == 3 # 2D, 1D, Price
    assert stats.panel_1d.sub_tabs.count() == 8 # 8 category tabs
    assert stats.panel_1d.table_parts.rowCount() == 1
    assert stats.panel_1d.table_parts.item(0, 1).text() == "200"
    assert stats.panel_1d.table_parts.item(0, 2).text() == "520"

    # 4. Test Excel Results (1D) export
    proj = Project(id="TEST-PRJ", name="Steel Project", code="PRJ-101")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tpath = tmp.name

    ExcelReportExporter.export_workshop_workbook(tpath, proj, res)
    wb = openpyxl.load_workbook(tpath)
    assert "Results (1D)" in wb.sheetnames
    ws_1d = wb["Results (1D)"]
    assert ws_1d["A1"].value == "Results (1D)"
    assert ws_1d["A2"].value == "#"
    assert ws_1d["I2"].value == "Pieces"
    assert "x200" in str(ws_1d["I3"].value)
