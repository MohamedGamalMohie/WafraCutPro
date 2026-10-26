"""
Part Requirements Data Models for Linear and Plate Cutting
"""
from dataclasses import dataclass, field
from typing import Optional
from steel_nest.config import MaterialType

@dataclass
class PartCutItem:
    """Represents a required linear cut part (e.g. beam, channel, pipe, column)."""
    id: str
    mark: str                      # Unique part mark e.g. B101, C205, P1
    designation: str               # e.g. IPE 300, HEA 200, SHS 100x100x6
    grade: str                     # e.g. S355JR
    length_mm: float               # Required cut length
    quantity: int = 1              # Number of identical pieces required
    assigned_qty: int = 0          # Number of pieces successfully nested
    weight_kg: float = 0.0         # Calculated or specified weight per part
    priority: int = 1              # Priority level (1 = highest)
    notes: str = ""

    @property
    def remaining_qty(self) -> int:
        return max(0, self.quantity - self.assigned_qty)

    @property
    def key(self) -> str:
        return f"{self.designation.strip().upper()}|{self.grade.strip().upper()}"

@dataclass
class PlatePartItem:
    """Represents a required rectangular plate part (e.g. base plate, gusset, stiffener)."""
    id: str
    mark: str                      # Unique mark e.g. BP-1, GUS-10
    thickness_mm: float            # Plate thickness in mm
    grade: str                     # e.g. S275JR
    width_mm: float                # Part width in mm
    length_mm: float               # Part length in mm
    quantity: int = 1              # Quantity required
    assigned_qty: int = 0
    allow_rotation: bool = True    # Allow 90 degree rotation
    grain_direction: str = "ANY"   # ANY (rotatable), HORIZONTAL (fixed along length), VERTICAL (fixed along width)
    edge_top: str = ""             # Edge banding top e.g. "1mm"
    edge_bottom: str = ""          # Edge banding bottom
    edge_left: str = ""            # Edge banding left
    edge_right: str = ""           # Edge banding right
    notes: str = ""

    @property
    def remaining_qty(self) -> int:
        return max(0, self.quantity - self.assigned_qty)

    @property
    def area_m2(self) -> float:
        return (self.width_mm * self.length_mm) / 1_000_000.0

    @property
    def key(self) -> str:
        clean_grade = self.grade.strip().upper()
        if self.thickness_mm > 0:
            return f"PL-{self.thickness_mm:.1f}mm|{clean_grade}"
        return clean_grade
