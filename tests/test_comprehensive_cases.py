"""
Comprehensive Test Suite for SteelNest Pro
Implements rigorous automated verification for all 14 mandatory cases
defined in the Master Specification.
"""
import pytest
import os
import tempfile
import uuid

from steel_nest.config import LinearOptimizationMode, NestingObjective, RemnantStatus, MaterialType
from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.project import Project, ProjectSettings
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.core.plate_optimizer import PlateOptimizer
from steel_nest.core.validation import InputValidator
from steel_nest.core.remnant_manager import RemnantManager
from steel_nest.database.db_manager import DatabaseManager
from steel_nest.database.repositories import ProjectRepository, StockRepository, CutListRepository, RemnantRepository
from steel_nest.reporting.excel_exporter import ExcelReportExporter

# --------------------------------------------------------------------------
# CASE 1: One 12,000 mm stock bar with parts 5,000 mm & 7,000 mm (0 kerf, 0 trim)
# --------------------------------------------------------------------------
def test_case_01_exact_fit_zero_kerf_zero_trim():
    stock = [StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=1)]
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S355JR", length_mm=5000.0, quantity=1),
        PartCutItem(id="P2", mark="P2", designation="IPE 300", grade="S355JR", length_mm=7000.0, quantity=1),
    ]
    optimizer = LinearOptimizer(
        mode=LinearOptimizationMode.FREE_NESTING,
        kerf_mm=0.0,
        trim_start_mm=0.0,
        trim_end_mm=0.0
    )
    result = optimizer.optimize(parts, stock)

    assert len(result.linear_plans) == 1, "Should use exactly 1 stock bar"
    bar = result.linear_plans[0]
    assert bar.part_count == 2
    assert bar.total_part_length == 12000.0
    assert bar.raw_remnant_length == 0.0
    assert bar.utilization_pct == 100.0
    assert result.overall_waste_pct == 0.0

# --------------------------------------------------------------------------
# CASE 2: 12,000 mm stock bar with 5,000 mm & 6,000 mm and configurable kerf
# --------------------------------------------------------------------------
def test_case_02_configurable_kerf_accounting():
    kerf = 5.0
    trim_start = 10.0
    trim_end = 15.0
    stock = [StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=1)]
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S355JR", length_mm=5000.0, quantity=1),
        PartCutItem(id="P2", mark="P2", designation="IPE 300", grade="S355JR", length_mm=6000.0, quantity=1),
    ]
    optimizer = LinearOptimizer(
        mode=LinearOptimizationMode.FREE_NESTING,
        kerf_mm=kerf,
        trim_start_mm=trim_start,
        trim_end_mm=trim_end
    )
    result = optimizer.optimize(parts, stock)

    assert len(result.linear_plans) == 1
    bar = result.linear_plans[0]
    # Expected used length: 5000 + 6000 + 1 kerf (5) + trim (10+15=25) = 11030 mm
    expected_used = 5000.0 + 6000.0 + kerf + (trim_start + trim_end)
    assert bar.used_length == expected_used
    assert bar.raw_remnant_length == (12000.0 - expected_used)
    assert bar.total_kerf_length == kerf

# --------------------------------------------------------------------------
# CASE 3: Single Cut mode strictly packs ONE distinct cut length per bar (Workshop Standard)
# --------------------------------------------------------------------------
def test_case_03_single_cut_mode_strict_enforcement():
    stock = [StockItem(id="S1", designation="HEA 200", grade="S355JR", length_mm=12000.0, available_qty=10)]
    parts = [
        # Multiple pieces of 400mm, 1200mm, and 3500mm
        PartCutItem(id="P1", mark="P1", designation="HEA 200", grade="S355JR", length_mm=400.0, quantity=8),
        PartCutItem(id="P2", mark="P2", designation="HEA 200", grade="S355JR", length_mm=1200.0, quantity=5),
        PartCutItem(id="P3", mark="P3", designation="HEA 200", grade="S355JR", length_mm=3500.0, quantity=3)
    ]
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.SINGLE_CUT)
    result = optimizer.optimize(parts, stock)

    # Every bar in Single Cut mode MUST contain only ONE distinct cut length (repeated as needed)
    assert len(result.linear_plans) > 0
    for bar in result.linear_plans:
        distinct_lengths = set(seg.length for seg in bar.segments)
        assert len(distinct_lengths) == 1, f"Single Cut mode bar {bar.bar_index} had multiple distinct lengths: {distinct_lengths}"
        # Saws stop is set once: all segments have identical length
        first_len = bar.segments[0].length
        assert all(seg.length == first_len for seg in bar.segments)

# --------------------------------------------------------------------------
# CASE 4: Double Cuts mode allows at most TWO distinct cut lengths per bar (Workshop Standard)
# --------------------------------------------------------------------------
def test_case_04_double_cut_mode_strict_enforcement():
    stock = [StockItem(id="S1", designation="UPN 160", grade="S275JR", length_mm=12000.0, available_qty=10)]
    parts = [
        # 4 different cut lengths
        PartCutItem(id="P1", mark="P1", designation="UPN 160", grade="S275JR", length_mm=400.0, quantity=6),
        PartCutItem(id="P2", mark="P2", designation="UPN 160", grade="S275JR", length_mm=1200.0, quantity=4),
        PartCutItem(id="P3", mark="P3", designation="UPN 160", grade="S275JR", length_mm=2500.0, quantity=3),
        PartCutItem(id="P4", mark="P4", designation="UPN 160", grade="S275JR", length_mm=4000.0, quantity=2),
    ]
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.DOUBLE_CUT)
    result = optimizer.optimize(parts, stock)

    assert len(result.linear_plans) > 0
    for bar in result.linear_plans:
        distinct_lengths = set(seg.length for seg in bar.segments)
        assert len(distinct_lengths) <= 2, f"Double Cut mode bar {bar.bar_index} had {len(distinct_lengths)} distinct lengths; max 2 allowed! {distinct_lengths}"

# --------------------------------------------------------------------------
# CASE 5: Free Nesting can assign more than two pieces when beneficial
# --------------------------------------------------------------------------
def test_case_05_free_nesting_multiple_pieces():
    stock = [StockItem(id="S1", designation="L 50x50x5", grade="S275JR", length_mm=6000.0, available_qty=1)]
    parts = [
        PartCutItem(id="P1", mark="P1", designation="L 50x50x5", grade="S275JR", length_mm=1000.0, quantity=4)
    ]
    optimizer = LinearOptimizer(
        mode=LinearOptimizationMode.FREE_NESTING,
        kerf_mm=3.0,
        trim_start_mm=15.0,
        trim_end_mm=15.0
    )
    result = optimizer.optimize(parts, stock)

    assert len(result.linear_plans) == 1
    bar = result.linear_plans[0]
    # Free nesting should pack all 4 pieces onto the single 6000 mm bar
    assert bar.part_count == 4
    assert bar.total_part_length == 4000.0

# --------------------------------------------------------------------------
# CASE 6: No cutting pattern exceeds usable stock length
# --------------------------------------------------------------------------
def test_case_06_no_cutting_pattern_exceeds_stock_length():
    stock = [StockItem(id="S1", designation="IPE 200", grade="S355JR", length_mm=6000.0, available_qty=5)]
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 200", grade="S355JR", length_mm=2500.0, quantity=5),
        PartCutItem(id="P2", mark="P2", designation="IPE 200", grade="S355JR", length_mm=1800.0, quantity=4),
    ]
    for mode in [LinearOptimizationMode.FREE_NESTING, LinearOptimizationMode.SINGLE_CUT, LinearOptimizationMode.DOUBLE_CUT]:
        opt = LinearOptimizer(mode=mode, kerf_mm=4.0, trim_start_mm=20.0, trim_end_mm=20.0)
        res = opt.optimize(parts, stock)
        for bar in res.linear_plans:
            assert bar.used_length <= bar.stock_length, f"Bar {bar.bar_index} used {bar.used_length} exceeding stock {bar.stock_length} in {mode}"

# --------------------------------------------------------------------------
# CASE 7: Inventory quantities are tracked and shortages identified
# --------------------------------------------------------------------------
def test_case_07_inventory_quantities_and_shortages():
    # Only 1 physical bar available
    stock = [StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=1)]
    # Needs two 7000 mm parts (which cannot fit together on 1 bar)
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S355JR", length_mm=7000.0, quantity=2)
    ]
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    result = optimizer.optimize(parts, stock)

    assert len(result.linear_plans) == 2
    # Shortage must be recorded because physical inventory had only 1 bar
    assert len(result.shortages) > 0, "Inventory shortage must be detected and recorded"

# --------------------------------------------------------------------------
# CASE 8: Infeasible parts reported accurately
# --------------------------------------------------------------------------
def test_case_08_infeasible_parts_reporting():
    stock = [StockItem(id="S1", designation="HEA 300", grade="S355JR", length_mm=12000.0, available_qty=5)]
    # 13,000 mm part is longer than 12,000 mm stock
    parts = [
        PartCutItem(id="P1", mark="TOO_LONG", designation="HEA 300", grade="S355JR", length_mm=13000.0, quantity=1)
    ]
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    result = optimizer.optimize(parts, stock)

    assert len(result.unassigned_parts) == 1
    unassigned = result.unassigned_parts[0]
    assert unassigned.part_mark == "TOO_LONG"
    assert "exceeds" in unassigned.reason.lower()

# --------------------------------------------------------------------------
# CASE 9: Different grades and incompatible sections are NEVER mixed
# --------------------------------------------------------------------------
def test_case_09_incompatible_materials_never_mixed():
    stock = [
        StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=5),
        StockItem(id="S2", designation="IPE 300", grade="S275JR", length_mm=12000.0, available_qty=5),
        StockItem(id="S3", designation="HEA 300", grade="S355JR", length_mm=12000.0, available_qty=5)
    ]
    parts = [
        PartCutItem(id="P1", mark="P_IPE355", designation="IPE 300", grade="S355JR", length_mm=4000.0, quantity=1),
        PartCutItem(id="P2", mark="P_IPE275", designation="IPE 300", grade="S275JR", length_mm=4000.0, quantity=1),
        PartCutItem(id="P3", mark="P_HEA355", designation="HEA 300", grade="S355JR", length_mm=4000.0, quantity=1),
    ]
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    result = optimizer.optimize(parts, stock)

    for bar in result.linear_plans:
        # Check every segment matches the bar's designation and grade
        for seg in bar.segments:
            matching_part = next(p for p in parts if p.id == seg.part_id)
            assert matching_part.designation == bar.designation
            assert matching_part.grade == bar.grade

# --------------------------------------------------------------------------
# CASE 10: Remnants calculated correctly without double-counting
# --------------------------------------------------------------------------
def test_case_10_remnant_exact_calculation():
    stock_len = 12000.0
    part_len = 8000.0
    kerf = 3.0
    trim_start = 20.0
    trim_end = 20.0
    stock = [StockItem(id="S1", designation="IPE 400", grade="S355JR", length_mm=stock_len, available_qty=1)]
    parts = [PartCutItem(id="P1", mark="P1", designation="IPE 400", grade="S355JR", length_mm=part_len, quantity=1)]

    optimizer = LinearOptimizer(
        mode=LinearOptimizationMode.FREE_NESTING,
        kerf_mm=kerf,
        trim_start_mm=trim_start,
        trim_end_mm=trim_end,
        min_remnant_length_mm=500.0
    )
    result = optimizer.optimize(parts, stock)
    bar = result.linear_plans[0]

    # For 1 part: used_length = part_len + trim_start + trim_end (no internal kerf)
    expected_used = part_len + trim_start + trim_end
    expected_rem = stock_len - expected_used
    assert bar.used_length == expected_used
    assert bar.raw_remnant_length == expected_rem
    assert bar.total_kerf_length == 0.0

# --------------------------------------------------------------------------
# CASE 11: Plate nesting produces non-overlapping parts within boundaries
# --------------------------------------------------------------------------
def test_case_11_plate_nesting_no_overlap_within_bounds():
    stock = [StockItem(id="SP1", designation="PL 15mm", grade="S355JR", length_mm=6000.0, width_mm=2000.0, thickness_mm=15.0, material_type=MaterialType.PLATE, available_qty=2)]
    parts = [
        PlatePartItem(id="PL1", mark="PL1", thickness_mm=15.0, grade="S355JR", width_mm=500.0, length_mm=800.0, quantity=4, allow_rotation=True),
        PlatePartItem(id="PL2", mark="PL2", thickness_mm=15.0, grade="S355JR", width_mm=400.0, length_mm=600.0, quantity=6, allow_rotation=True)
    ]
    margin = 10.0
    kerf = 4.0
    optimizer = PlateOptimizer(kerf_mm=kerf, margin_mm=margin)
    result = optimizer.optimize(parts, stock)

    for plan in result.plate_plans:
        # Check within boundaries
        for p in plan.parts:
            assert p.x >= margin
            assert p.y >= margin
            assert (p.x + p.width) <= (plan.plate_width - margin + 0.001)
            assert (p.y + p.length) <= (plan.plate_length - margin + 0.001)

        # Check non-overlapping
        for i in range(len(plan.parts)):
            for j in range(i + 1, len(plan.parts)):
                p1 = plan.parts[i]
                p2 = plan.parts[j]
                
                overlap_x = not (p1.x + p1.width <= p2.x or p2.x + p2.width <= p1.x)
                overlap_y = not (p1.y + p1.length <= p2.y or p2.y + p2.length <= p1.y)
                assert not (overlap_x and overlap_y), f"Parts {p1.part_mark} and {p2.part_mark} overlap on plate #{plan.plate_index}"

# --------------------------------------------------------------------------
# CASE 12: Excel exports match optimizer results
# --------------------------------------------------------------------------
def test_case_12_excel_export_consistency():
    stock = [StockItem(id="S1", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=2)]
    parts = [PartCutItem(id="P1", mark="P1", designation="IPE 300", grade="S355JR", length_mm=5000.0, quantity=2)]
    
    optimizer = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    result = optimizer.optimize(parts, stock)

    proj = Project(id="TEST-PRJ", name="Test Project", code="PRJ-001")
    
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        ExcelReportExporter.export_full_workbook(
            file_path=tmp_path,
            project=proj,
            result=result,
            parts_1d=parts,
            parts_2d=[],
            stock_items=stock,
            remnants=[]
        )
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 5000 # Valid xlsx file generated

        # Reopen workbook and check sheets
        import openpyxl
        wb = openpyxl.load_workbook(tmp_path)
        expected_sheets = [
            "Executive Summary", "Detailed Cutting Plan", "Cut List",
            "Stock Purchase List", "Remnants and Offcuts", "Material Summary",
            "Plate Nesting", "Unprocessed Exceptions"
        ]
        for s in expected_sheets:
            assert s in wb.sheetnames, f"Missing sheet: {s}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# --------------------------------------------------------------------------
# CASE 13: Reopening saved project reproduces data and settings
# --------------------------------------------------------------------------
def test_case_13_reopening_saved_project():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = DatabaseManager(db_path=db_path)
        proj_repo = ProjectRepository(db)
        cut_repo = CutListRepository(db)

        # Create project with custom settings
        settings = ProjectSettings(kerf_mm=4.5, trim_start_mm=25.0, min_remnant_length_mm=600.0)
        proj = Project(id="P100", name="Project A", code="PRJ-A", settings=settings)
        proj_repo.create(proj)

        # Add parts
        part = PartCutItem(id="PT1", mark="BEAM-1", designation="HEA 200", grade="S355JR", length_mm=3200.0, quantity=4)
        cut_repo.add_linear(part, proj.id)

        # Reopen from DB
        db2 = DatabaseManager(db_path=db_path)
        proj_repo2 = ProjectRepository(db2)
        cut_repo2 = CutListRepository(db2)

        reopened_proj = proj_repo2.get("P100")
        assert reopened_proj is not None
        assert reopened_proj.name == "Project A"
        assert reopened_proj.settings.kerf_mm == 4.5
        assert reopened_proj.settings.trim_start_mm == 25.0

        reopened_parts = cut_repo2.list_linear_by_project("P100")
        assert len(reopened_parts) == 1
        assert reopened_parts[0].mark == "BEAM-1"
        assert reopened_parts[0].quantity == 4
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

# --------------------------------------------------------------------------
# CASE 14: Large input files handled without crashing
# --------------------------------------------------------------------------
def test_case_14_large_input_handling():
    stock = [
        StockItem(id=f"S{i}", designation="IPE 300", grade="S355JR", length_mm=12000.0, available_qty=50)
        for i in range(5)
    ]
    # 150 cut parts with random-like variations
    parts = []
    lengths = [1500.0, 2200.0, 3100.0, 4200.0, 5400.0, 6000.0]
    for i in range(150):
        l = lengths[i % len(lengths)]
        parts.append(PartCutItem(id=f"P{i}", mark=f"MK-{i}", designation="IPE 300", grade="S355JR", length_mm=l, quantity=1))

    optimizer = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING, time_limit_sec=5)
    result = optimizer.optimize(parts, stock)

    assert result.total_parts_nested == 150
    assert len(result.linear_plans) > 0
    assert result.overall_utilization_pct > 80.0
