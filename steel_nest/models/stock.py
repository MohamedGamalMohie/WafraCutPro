"""
Stock and Remnant Inventory Data Models
"""
from dataclasses import dataclass, field
from typing import Optional
from steel_nest.config import RemnantStatus, MaterialType

@dataclass
class StockItem:
    """Represents a standard stock item or remnant available in inventory."""
    id: str
    designation: str
    grade: str
    length_mm: float
    width_mm: float = 0.0          # Used for plates (0 for linear profiles)
    thickness_mm: float = 0.0      # Used for plates
    available_qty: int = 1
    used_qty: int = 0
    cost_per_unit: float = 0.0
    is_remnant: bool = False
    source_project: str = ""
    location: str = "Warehouse A"
    material_type: MaterialType = MaterialType.LINEAR
    notes: str = ""

    @property
    def remaining_qty(self) -> int:
        return max(0, self.available_qty - self.used_qty)

    @property
    def key(self) -> str:
        clean_grade = self.grade.strip().upper()
        if self.material_type == MaterialType.PLATE or self.width_mm > 0:
            if self.thickness_mm > 0:
                return f"PL-{self.thickness_mm:.1f}mm|{clean_grade}"
            return clean_grade
        return f"{self.designation.strip().upper()}|{clean_grade}"

@dataclass
class RemnantItem:
    """Usable remnant generated from cutting plans."""
    id: str
    original_stock_id: str
    designation: str
    grade: str
    length_mm: float
    width_mm: float = 0.0
    thickness_mm: float = 0.0
    material_type: MaterialType = MaterialType.LINEAR
    status: RemnantStatus = RemnantStatus.REUSABLE
    created_date: str = ""
    source_project: str = ""
    location: str = "Remnants Rack"
    notes: str = ""

    @property
    def is_reusable(self) -> bool:
        return self.status == RemnantStatus.REUSABLE
