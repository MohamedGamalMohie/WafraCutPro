"""
Material and Profile Data Models for SteelNest Pro
"""
from dataclasses import dataclass, field
from typing import Optional
from steel_nest.config import MaterialType

@dataclass
class SteelProfile:
    """Represents a steel profile specification (e.g. IPE 300, S355JR)."""
    designation: str
    family: str  # IPE, HEA, HEB, UPN, L, SHS, RHS, CHS, FLAT, ROUND, PLATE
    grade: str
    weight_kg_per_m: float = 0.0
    material_type: MaterialType = MaterialType.LINEAR
    notes: str = ""

    @property
    def key(self) -> str:
        """Unique key grouping compatible materials."""
        return f"{self.designation.strip().upper()}|{self.grade.strip().upper()}"

@dataclass
class PlateSpecification:
    """Specification for steel plates."""
    thickness_mm: float
    grade: str
    density_kg_per_m3: float = 7850.0  # standard mild steel density
    notes: str = ""

    @property
    def key(self) -> str:
        return f"PL-{self.thickness_mm}mm|{self.grade.strip().upper()}"
