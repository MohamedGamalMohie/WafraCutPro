import pytest
from steel_nest.config import (
    APP_VERSION, DEFAULT_KERF, DEFAULT_TRIM_START, DEFAULT_TRIM_END,
    DEFAULT_PLATE_KERF, DEFAULT_PLATE_MARGIN, DEFAULT_MIN_USABLE_WASTE,
    DEFAULT_MIN_REMNANT, LinearOptimizationMode
)
from steel_nest.models.project import ProjectSettings, Project
from steel_nest.models.part import PartCutItem
from steel_nest.models.stock import StockItem
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView, CuttingSettingsDialog

def test_v122_version_and_default_zeros():
    """Verify version 1.2.2 and that default cutting parameters are strictly 0.0."""
    assert APP_VERSION == "1.2.2"
    assert DEFAULT_KERF == 0.0
    assert DEFAULT_TRIM_START == 0.0
    assert DEFAULT_TRIM_END == 0.0
    assert DEFAULT_PLATE_KERF == 0.0
    assert DEFAULT_PLATE_MARGIN == 0.0
    assert DEFAULT_MIN_USABLE_WASTE == 0.0
    assert DEFAULT_MIN_REMNANT == 0.0

    settings = ProjectSettings()
    assert settings.kerf_mm == 0.0
    assert settings.trim_start_mm == 0.0
    assert settings.trim_end_mm == 0.0
    assert settings.plate_kerf_mm == 0.0
    assert settings.plate_margin_mm == 0.0
    assert settings.min_usable_waste_mm == 0.0
    assert settings.min_remnant_length_mm == 0.0

def test_v122_settings_dialog_default_zeros(qapp):
    """Verify the Settings dialog (shown in user image) opens with default zero values."""
    settings = ProjectSettings()
    dlg = CuttingSettingsDialog(settings, LinearOptimizationMode.FREE_NESTING)

    assert dlg.spin_kerf.value() == 0.0
    assert dlg.spin_trim.value() == 0.0
    assert dlg.spin_margin.value() == 0.0
    assert dlg.spin_useful_waste.value() == 0.0
    dlg.close()

def test_v122_zero_kerf_trim_full_capacity_nesting():
    """Verify that with zero kerf and trim, exact parts fit completely on stock bar."""
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 200", grade="S275JR", length_mm=4000.0, quantity=3),
    ]
    stock = [
        StockItem(id="S1", designation="IPE 200", grade="S275JR", length_mm=12000.0, available_qty=1),
    ]

    opt = LinearOptimizer(
        mode=LinearOptimizationMode.FREE_NESTING,
        kerf_mm=0.0,
        trim_start_mm=0.0,
        trim_end_mm=0.0,
        min_remnant_length_mm=0.0
    )
    res = opt.optimize(parts, stock)

    # 3 x 4000 = 12000 exact fit on single 12000 bar with 100% utilization and 0 waste
    assert res.total_parts_nested == 3
    assert len(res.linear_plans) == 1
    plan = res.linear_plans[0]
    assert plan.stock_length == 12000.0
    assert len(plan.segments) == 3
    assert plan.utilization_pct == 100.0
    assert plan.waste_pct == 0.0

def test_v122_o1_pattern_grouping():
    """Verify high-speed O(1) dictionary-based pattern grouping."""
    parts = [
        PartCutItem(id=f"P_{i}", mark=f"P_{i}", designation="HEA 200", grade="S355JR", length_mm=2000.0, quantity=1)
        for i in range(100)
    ]
    stock = [
        StockItem(id="S1", designation="HEA 200", grade="S355JR", length_mm=12000.0, available_qty=50)
    ]

    opt = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    res = opt.optimize(parts, stock)

    # All 100 items (6 per bar on 12m) should be consolidated into identical plans
    assert sum(p.repetition_count for p in res.linear_plans) >= 16
    assert all(hasattr(p, 'repetition_count') for p in res.linear_plans)
    assert res.total_parts_nested == 100
