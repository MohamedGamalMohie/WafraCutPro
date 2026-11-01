"""
Project and Project Settings Models
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from steel_nest.config import (
    DEFAULT_KERF, DEFAULT_TRIM_START, DEFAULT_TRIM_END,
    DEFAULT_MIN_REMNANT, DEFAULT_TIME_LIMIT_SEC,
    DEFAULT_PLATE_KERF, DEFAULT_PLATE_MARGIN, DEFAULT_MIN_USABLE_WASTE,
    LinearOptimizationMode, NestingObjective
)

@dataclass
class ProjectSettings:
    """Project-level cutting parameters and constraints."""
    kerf_mm: float = DEFAULT_KERF
    trim_start_mm: float = DEFAULT_TRIM_START
    trim_end_mm: float = DEFAULT_TRIM_END
    min_remnant_length_mm: float = DEFAULT_MIN_REMNANT
    plate_kerf_mm: float = DEFAULT_PLATE_KERF
    plate_margin_mm: float = DEFAULT_PLATE_MARGIN
    linear_mode: LinearOptimizationMode = LinearOptimizationMode.FREE_NESTING
    objective: NestingObjective = NestingObjective.MIN_WASTE
    time_limit_sec: int = DEFAULT_TIME_LIMIT_SEC
    allow_remnants_use: bool = True
    guillotine_cuts_only: bool = False
    guillotine_first_cut: str = "AUTO"          # AUTO, HORIZONTAL, VERTICAL
    guillotine_stages: int = 2                  # 2-stage, 3-stage, multi-stage
    optimization_level: int = 5                 # 1 (Fast) to 10 (Deep search)
    max_cut_length_mm: float = 0.0              # Maximum cut length for manual/table saws
    min_breakable_waste_mm: float = 0.0         # Avoid thin breakable slivers (glass/ceramics)
    min_usable_waste_mm: float = DEFAULT_MIN_USABLE_WASTE  # Below this is garbage, above is reusable (Default: 0.0)
    metric_unit: str = "GENERAL"                # GENERAL (unitless), MM, INCH
    language: str = "AR"                        # AR, EN, FR
    color_mode: str = "COLOR"                   # COLOR, BW
    group_identical_layouts: bool = True        # Group identical cutting patterns

@dataclass
class Project:
    """WafraCut Pro Project container."""
    id: str
    name: str
    code: str
    client: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    settings: ProjectSettings = field(default_factory=ProjectSettings)
