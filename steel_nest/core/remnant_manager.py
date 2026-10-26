"""
Remnant and Offcut Tracking Manager
"""
import uuid
from datetime import datetime
from typing import List, Tuple
from steel_nest.models.nesting_plan import LinearBarPlan, PlateNestPlan
from steel_nest.models.stock import RemnantItem
from steel_nest.config import RemnantStatus, MaterialType
from steel_nest.database.repositories import RemnantRepository, StockRepository

class RemnantManager:
    def __init__(self, remnant_repo: RemnantRepository, stock_repo: StockRepository):
        self.remnant_repo = remnant_repo
        self.stock_repo = stock_repo

    def extract_reusable_remnants(
        self,
        linear_plans: List[LinearBarPlan],
        min_remnant_length_mm: float,
        project_name: str = ""
    ) -> List[RemnantItem]:
        """
        Extracts offcuts that meet or exceed minimum reusable threshold.
        """
        remnants: List[RemnantItem] = []
        for plan in linear_plans:
            raw_rem = plan.raw_remnant_length
            if raw_rem >= min_remnant_length_mm:
                rem_id = f"REM-{plan.designation.replace(' ', '')}-{int(raw_rem)}-{uuid.uuid4().hex[:6]}"
                rem = RemnantItem(
                    id=rem_id,
                    original_stock_id=plan.stock_id,
                    designation=plan.designation,
                    grade=plan.grade,
                    length_mm=raw_rem,
                    width_mm=0.0,
                    thickness_mm=0.0,
                    material_type=MaterialType.LINEAR,
                    status=RemnantStatus.REUSABLE,
                    created_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    source_project=project_name,
                    location="Remnant Rack A",
                    notes=f"Generated from bar #{plan.bar_index} ({plan.stock_id})"
                )
                remnants.append(rem)
        return remnants

    def save_remnants_to_inventory(self, remnants: List[RemnantItem]):
        """Persists reusable remnants into the database and stock inventory."""
        for r in remnants:
            self.remnant_repo.add(r)
            # Add to stock inventory so future nesting runs can pick it up
            from steel_nest.models.stock import StockItem
            stock_item = StockItem(
                id=r.id,
                designation=r.designation,
                grade=r.grade,
                length_mm=r.length_mm,
                width_mm=r.width_mm,
                thickness_mm=r.thickness_mm,
                available_qty=1,
                used_qty=0,
                cost_per_unit=0.0,
                is_remnant=True,
                source_project=r.source_project,
                location=r.location,
                material_type=r.material_type,
                notes=r.notes
            )
            self.stock_repo.add(stock_item)
