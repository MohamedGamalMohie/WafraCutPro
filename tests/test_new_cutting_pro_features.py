"""
Unit tests for Cutting Optimization Pro advanced features in SteelNest Pro:
- Fractional & Unitless numeric parsing
- Guillotine packing vs Nested CAD packing
- Similar layout grouping with repetition counts
- Complex parametric product calculation
- Vector icon generation
"""
import pytest
from steel_nest.core.fractional_parser import parse_fractional_value, format_fractional_display
from steel_nest.core.plate_optimizer import PlateOptimizer, GuillotinePlatePacker, MaxRectsBin
from steel_nest.models.part import PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.ui.icon_manager import IconManager
from steel_nest.ui.i18n import t, set_current_language, get_current_language

def test_fractional_parser():
    # Integer
    assert parse_fractional_value("100") == 100.0
    # Decimals with period and comma
    assert parse_fractional_value("100.5") == 100.5
    assert parse_fractional_value("100,5") == 100.5
    # Mixed fraction
    assert parse_fractional_value("100 1/2") == 100.5
    assert parse_fractional_value("45 3/8") == 45.375
    # Simple fraction
    assert parse_fractional_value("3/4") == 0.75
    # With unit suffixes
    assert parse_fractional_value("1200 mm") == 1200.0
    assert parse_fractional_value("10 1/2\"") == 10.5
    assert parse_fractional_value("48 in") == 48.0
    # Formatter
    assert format_fractional_display(100.5) == "100 1/2"
    assert format_fractional_display(100.0) == "100"

def test_guillotine_plate_packer():
    packer = GuillotinePlatePacker(
        margin=0.0,
        kerf=2.0,
        first_cut="HORIZONTAL",
        stages=2
    )
    items = [
        {"id": "p1", "mark": "P1", "width": 400.0, "length": 600.0, "allow_rotation": True, "part_obj": None},
        {"id": "p2", "mark": "P2", "width": 400.0, "length": 600.0, "allow_rotation": True, "part_obj": None},
        {"id": "p3", "mark": "P3", "width": 500.0, "length": 800.0, "allow_rotation": True, "part_obj": None},
    ]
    placed, cuts, wastes, unplaced = packer.pack_plate(1000.0, 2000.0, items)
    assert len(placed) == 3
    assert len(unplaced) == 0
    # Verify cut lines generated
    assert len(cuts) > 0
    assert sum(c["length"] for c in cuts) > 0

def test_plate_optimizer_guillotine_mode():
    opt = PlateOptimizer(
        kerf_mm=3.0,
        margin_mm=5.0,
        guillotine_cuts_only=True,
        guillotine_first_cut="AUTO",
        guillotine_stages=2,
        group_identical_layouts=True
    )
    parts = [
        PlatePartItem(
            id="p1", mark="P1", thickness_mm=12.0, grade="S275JR",
            width_mm=400.0, length_mm=600.0, quantity=4, allow_rotation=True
        ),
        PlatePartItem(
            id="p2", mark="P2", thickness_mm=12.0, grade="S275JR",
            width_mm=500.0, length_mm=700.0, quantity=4, allow_rotation=True
        ),
    ]
    stock = [
        StockItem(
            id="PL-1", designation="PL 12mm", grade="S275JR",
            width_mm=1500.0, length_mm=3000.0, thickness_mm=12.0, available_qty=5
        )
    ]
    res = opt.optimize(parts, stock)
    assert len(res.plate_plans) > 0
    assert res.overall_utilization_pct > 0
    for pl in res.plate_plans:
        assert pl.is_guillotine is True
        assert pl.total_cut_distance > 0

def test_group_identical_layouts():
    opt = PlateOptimizer(
        kerf_mm=0.0,
        margin_mm=0.0,
        guillotine_cuts_only=False,
        group_identical_layouts=True
    )
    # 20 identical parts packed into multiple stock plates
    parts = [
        PlatePartItem(
            id=f"part-{i}", mark=f"P-{i}", thickness_mm=10.0, grade="S275JR",
            width_mm=500.0, length_mm=1000.0, quantity=1, allow_rotation=False
        ) for i in range(20)
    ]
    stock = [
        StockItem(
            id="PL-STOCK", designation="PL 10mm", grade="S275JR",
            width_mm=1000.0, length_mm=2000.0, thickness_mm=10.0, available_qty=10
        )
    ]
    res = opt.optimize(parts, stock)
    # Plans should be grouped with repetition_count > 1
    total_reps = sum(pl.repetition_count for pl in res.plate_plans)
    assert total_reps >= 5
    # The number of distinct plans should be fewer than total repetitions
    assert len(res.plate_plans) < total_reps

def test_i18n_translations():
    set_current_language("AR")
    assert "قطع مقصلة" in t("guillotine_opt")
    set_current_language("EN")
    assert "Guillotine" in t("guillotine_opt")
    set_current_language("FR")
    assert "Guillotine" in t("guillotine_opt")
    set_current_language("AR") # Reset

def test_icon_manager():
    # Test vector icon generation
    icon_start = IconManager.get_icon("start", 16)
    assert not icon_start.isNull()
    icon_cnc = IconManager.get_icon("cnc", 16)
    assert not icon_cnc.isNull()
    icon_multi = IconManager.get_icon("multi_print", 16)
    assert not icon_multi.isNull()
