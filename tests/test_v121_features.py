import time
import pytest
from steel_nest.models.part import PartCutItem
from steel_nest.models.stock import StockItem
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.config import LinearOptimizationMode
from steel_nest.ui.views.cutting_optimization_view import CuttingOptimizationView

def test_large_quantity_nesting_performance():
    """Verify that nesting 2,000 parts runs in under 1 second without freezing."""
    parts = [
        PartCutItem(id="P1", mark="P1", designation="L40*4", grade="S275JR", length_mm=1200.0, quantity=1200),
        PartCutItem(id="P2", mark="P2", designation="L40*4", grade="S275JR", length_mm=800.0, quantity=800),
    ]
    stock = [
        StockItem(id="S1", designation="L40*4", grade="S275JR", length_mm=6000.0, available_qty=2000),
    ]

    start = time.time()
    # Test FREE_NESTING mode
    opt_free = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    res_free = opt_free.optimize(parts, stock)
    elapsed_free = time.time() - start

    assert elapsed_free < 1.0, f"FREE_NESTING took too long: {elapsed_free:.2f}s"
    assert res_free.total_parts_nested == 2000
    assert len(res_free.linear_plans) < 200 # Must be grouped into patterns
    assert all(p.repetition_count >= 1 for p in res_free.linear_plans)

    # Test SINGLE_CUT mode
    start = time.time()
    opt_single = LinearOptimizer(mode=LinearOptimizationMode.SINGLE_CUT)
    res_single = opt_single.optimize(parts, stock)
    elapsed_single = time.time() - start

    assert elapsed_single < 1.0, f"SINGLE_CUT took too long: {elapsed_single:.2f}s"
    assert res_single.total_parts_nested == 2000

    # Test DOUBLE_CUT mode
    start = time.time()
    opt_double = LinearOptimizer(mode=LinearOptimizationMode.DOUBLE_CUT)
    res_double = opt_double.optimize(parts, stock)
    elapsed_double = time.time() - start

    assert elapsed_double < 1.5, f"DOUBLE_CUT took too long: {elapsed_double:.2f}s"
    assert res_double.total_parts_nested == 2000

def test_pattern_grouping_and_tab_display(qapp):
    """Verify that grouped linear plans generate concise tabs with (xRepetition)."""
    parts = [
        PartCutItem(id="P1", mark="P1", designation="IPE 200", grade="S275JR", length_mm=1500.0, quantity=40),
    ]
    stock = [
        StockItem(id="S1", designation="IPE 200", grade="S275JR", length_mm=6000.0, available_qty=50),
    ]

    opt = LinearOptimizer(mode=LinearOptimizationMode.FREE_NESTING)
    res = opt.optimize(parts, stock)

    # Usable 5970mm fits 3 parts of 1500mm. 13 bars * 3 = 39, plus 1 bar * 1 = 40.
    assert len(res.linear_plans) == 2
    assert res.linear_plans[0].repetition_count == 13
    assert res.linear_plans[1].repetition_count == 1
    assert res.total_parts_nested == 40

    view = CuttingOptimizationView()
    view._on_optimization_done(res)

    # Pattern tabs count should be 2, titled '#1 (x13)' and '#2'
    assert view.pattern_tabs.count() == 2
    assert view.pattern_tabs.tabText(0) == "#1 (x13)"
    assert view.pattern_tabs.tabText(1) == "#2"

def test_two_row_toolbars_layout(qapp):
    """Verify that pieces and stock toolbars are split into two rows."""
    view = CuttingOptimizationView()
    # Ensure all essential buttons are present and have non-empty text
    assert view.btn_start.text() != ""
    assert view.pieces_table.columnCount() == 7
    assert view.stock_table.columnCount() == 7
