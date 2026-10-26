"""
Input Validation and Sanity Checking Module
"""
from typing import List, Tuple, Dict, Any, Optional
from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.models.nesting_plan import UnassignedPart

class InputValidator:
    @staticmethod
    def validate_linear_inputs(
        parts: List[PartCutItem],
        stock: List[StockItem],
        kerf: float,
        trim_start: float,
        trim_end: float
    ) -> Tuple[List[PartCutItem], List[UnassignedPart], List[str]]:
        """
        Validates linear parts against stock.
        Returns:
            - Valid parts eligible for nesting
            - Unassigned / Infeasible parts with clear explanations
            - General warning messages
        """
        valid_parts: List[PartCutItem] = []
        infeasible_parts: List[UnassignedPart] = []
        warnings: List[str] = []

        total_trim = trim_start + trim_end

        # Map available stock maximum length per material key
        max_stock_by_key: Dict[str, float] = {}
        stock_keys = set()
        for s in stock:
            if s.available_qty > s.used_qty:
                k = s.key
                stock_keys.add(k)
                if k not in max_stock_by_key or s.length_mm > max_stock_by_key[k]:
                    max_stock_by_key[k] = s.length_mm

        for part in parts:
            if part.quantity <= 0:
                warnings.append(f"Part {part.mark} has zero or negative quantity ({part.quantity}). Skipped.")
                continue

            if part.length_mm <= 0:
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=part.designation,
                    grade=part.grade,
                    length_or_dims=f"{part.length_mm} mm",
                    quantity=part.quantity,
                    reason=f"Invalid length ({part.length_mm} mm). Must be greater than zero."
                ))
                continue

            k = part.key
            if k not in stock_keys:
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=part.designation,
                    grade=part.grade,
                    length_or_dims=f"{part.length_mm} mm",
                    quantity=part.quantity,
                    reason=f"No compatible stock available in inventory for section '{part.designation}' and grade '{part.grade}'."
                ))
                continue

            max_len = max_stock_by_key[k]
            usable_max_len = max_len - total_trim
            if part.length_mm > usable_max_len:
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=part.designation,
                    grade=part.grade,
                    length_or_dims=f"{part.length_mm} mm",
                    quantity=part.quantity,
                    reason=f"Part length ({part.length_mm} mm) + Trimming ({total_trim} mm) exceeds maximum compatible stock bar length ({max_len} mm)."
                ))
                continue

            valid_parts.append(part)

        return valid_parts, infeasible_parts, warnings

    @staticmethod
    def validate_plate_inputs(
        parts: List[PlatePartItem],
        stock: List[StockItem],
        margin: float,
        kerf: float
    ) -> Tuple[List[PlatePartItem], List[UnassignedPart], List[str]]:
        """
        Validates 2D plate parts against available stock plates.
        """
        valid_parts: List[PlatePartItem] = []
        infeasible_parts: List[UnassignedPart] = []
        warnings: List[str] = []

        # Find max plate dimensions per key and per clean grade
        max_plate_dims: Dict[str, Tuple[float, float]] = {}
        max_plate_by_grade: Dict[str, Tuple[float, float]] = {}
        for s in stock:
            if s.available_qty > s.used_qty and s.width_mm > 0:
                k = s.key
                curr_w, curr_l = max_plate_dims.get(k, (0.0, 0.0))
                max_plate_dims[k] = (max(curr_w, s.width_mm), max(curr_l, s.length_mm))
                
                cg = s.grade.strip().upper()
                gw, gl = max_plate_by_grade.get(cg, (0.0, 0.0))
                max_plate_by_grade[cg] = (max(gw, s.width_mm), max(gl, s.length_mm))

        for part in parts:
            if part.quantity <= 0 or part.width_mm <= 0 or part.length_mm <= 0:
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=f"Plate {part.thickness_mm}mm",
                    grade=part.grade,
                    length_or_dims=f"{part.width_mm}x{part.length_mm} mm",
                    quantity=part.quantity,
                    reason="Invalid plate part dimensions or non-positive quantity."
                ))
                continue

            k = part.key
            cg = part.grade.strip().upper()
            
            # Lookup dimension limits by key or grade
            if k in max_plate_dims:
                max_w, max_l = max_plate_dims[k]
            elif cg in max_plate_by_grade:
                max_w, max_l = max_plate_by_grade[cg]
            else:
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=f"Plate {part.thickness_mm}mm",
                    grade=part.grade,
                    length_or_dims=f"{part.width_mm}x{part.length_mm} mm",
                    quantity=part.quantity,
                    reason=f"No stock plate with material '{part.grade}' available in inventory."
                ))
                continue
            usable_w = max_w - 2 * margin
            usable_l = max_l - 2 * margin

            # Check fit either regular or rotated
            fits_regular = (part.width_mm <= usable_w and part.length_mm <= usable_l)
            fits_rotated = part.allow_rotation and (part.length_mm <= usable_w and part.width_mm <= usable_l)

            if not (fits_regular or fits_rotated):
                infeasible_parts.append(UnassignedPart(
                    part_id=part.id,
                    part_mark=part.mark,
                    designation=f"Plate {part.thickness_mm}mm",
                    grade=part.grade,
                    length_or_dims=f"{part.width_mm}x{part.length_mm} mm",
                    quantity=part.quantity,
                    reason=f"Part dimensions exceed available usable plate dimensions ({usable_w:.0f}x{usable_l:.0f} mm)."
                ))
                continue

            valid_parts.append(part)

        return valid_parts, infeasible_parts, warnings
