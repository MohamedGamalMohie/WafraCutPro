"""
Nesting Plan and Pattern Models
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from steel_nest.config import LinearOptimizationMode, NestingObjective

@dataclass
class CutSegment:
    """A single cut piece placed on a stock bar."""
    part_id: str
    part_mark: str
    start_pos: float               # mm from bar start (including trim)
    end_pos: float                 # mm from bar start
    length: float                  # mm cut length
    kerf_after: float = 0.0        # mm saw blade kerf following this cut

@dataclass
class LinearBarPlan:
    """Cutting plan for an individual stock bar."""
    bar_index: int                 # 1-based bar index in current run
    stock_id: str
    designation: str
    grade: str
    stock_length: float            # Total raw stock length
    trim_start: float              # Start trim allowance
    trim_end: float                # End trim allowance
    kerf: float                    # Kerf applied between cuts
    segments: List[CutSegment] = field(default_factory=list)
    is_remnant_stock: bool = False # Whether the stock bar itself was from remnants
    unit_cost: float = 0.0
    repetition_count: int = 1      # Number of identical bars with this cut pattern
    total_cut_length: float = 0.0

    @property
    def part_count(self) -> int:
        return len(self.segments)

    @property
    def total_part_length(self) -> float:
        return sum(s.length for s in self.segments)

    @property
    def total_kerf_length(self) -> float:
        if len(self.segments) <= 1:
            return 0.0
        # Kerf exists between cuts
        return sum(s.kerf_after for s in self.segments[:-1])

    @property
    def total_trim_length(self) -> float:
        return self.trim_start + self.trim_end

    @property
    def used_length(self) -> float:
        # Usable length consumed by cuts + internal kerfs + trims
        return self.total_part_length + self.total_kerf_length + self.total_trim_length

    @property
    def raw_remnant_length(self) -> float:
        return max(0.0, self.stock_length - self.used_length)

    @property
    def utilization_pct(self) -> float:
        if self.stock_length <= 0:
            return 0.0
        return (self.total_part_length / self.stock_length) * 100.0

    @property
    def waste_pct(self) -> float:
        return max(0.0, 100.0 - self.utilization_pct)

    @property
    def waste_length(self) -> float:
        return self.raw_remnant_length

@dataclass
class PlacedPlatePart:
    """A rectangular part positioned on a plate."""
    part_id: str
    part_mark: str
    x: float                       # mm from left edge
    y: float                       # mm from bottom edge
    width: float                   # positioned width
    length: float                  # positioned length
    rotated: bool = False          # True if rotated 90 degrees

    @property
    def area_m2(self) -> float:
        return (self.width * self.length) / 1_000_000.0

@dataclass
class PlateNestPlan:
    """Layout plan for a single plate."""
    plate_index: int
    stock_id: str
    thickness_mm: float
    grade: str
    plate_width: float             # mm
    plate_length: float            # mm
    margin: float                  # mm border margin
    kerf: float                    # mm cutter kerf
    parts: List[PlacedPlatePart] = field(default_factory=list)
    unit_cost: float = 0.0
    repetition_count: int = 1      # Number of identical sheets with this nesting pattern
    total_cut_length: float = 0.0  # Total saw/cutter travel length in mm
    is_guillotine: bool = False    # Whether plan uses guillotine cuts (edge-to-edge)
    cut_lines: List[Dict[str, Any]] = field(default_factory=list)  # Ordered CNC cut sequence
    waste_rects: List[Dict[str, Any]] = field(default_factory=list) # Remnant / waste rectangles (x, y, w, l)

    @property
    def total_cut_distance(self) -> float:
        return self.total_cut_length

    @property
    def part_count(self) -> int:
        return len(self.parts)

    @property
    def total_plate_area_m2(self) -> float:
        return (self.plate_width * self.plate_length) / 1_000_000.0

    @property
    def used_parts_area_m2(self) -> float:
        return sum(p.area_m2 for p in self.parts)

    @property
    def utilization_pct(self) -> float:
        if self.total_plate_area_m2 <= 0:
            return 0.0
        return (self.used_parts_area_m2 / self.total_plate_area_m2) * 100.0

    @property
    def waste_pct(self) -> float:
        return max(0.0, 100.0 - self.utilization_pct)

    @property
    def waste_area(self) -> float:
        return max(0.0, (self.plate_width * self.plate_length) - sum(p.width * p.length for p in self.parts))

@dataclass
class UnassignedPart:
    """A part that could not be nested with a clear reason."""
    part_id: str
    part_mark: str
    designation: str
    grade: str
    length_or_dims: str
    quantity: int
    reason: str

@dataclass
class OptimizationResult:
    """Comprehensive result of an optimization run."""
    run_id: str
    project_id: str
    created_at: str
    mode: str                      # FREE_NESTING, SINGLE_CUT, DOUBLE_CUT, or PLATE_2D
    objective: str
    execution_time_sec: float
    is_proven_optimal: bool
    solver_status: str

    # 1D Linear Results
    linear_plans: List[LinearBarPlan] = field(default_factory=list)

    # 2D Plate Results
    plate_plans: List[PlateNestPlan] = field(default_factory=list)

    # Exception / Infeasible parts
    unassigned_parts: List[UnassignedPart] = field(default_factory=list)

    # Summary Metrics
    total_parts_required: int = 0
    total_parts_nested: int = 0
    total_stock_used: int = 0
    total_material_length_m: float = 0.0
    total_parts_length_m: float = 0.0
    total_reusable_remnants_length_m: float = 0.0
    total_unusable_waste_length_m: float = 0.0
    overall_utilization_pct: float = 0.0
    overall_waste_pct: float = 0.0
    total_estimated_cost: float = 0.0
    shortages: Dict[str, int] = field(default_factory=dict)
