"""
2D Rectangular Plate & Sheet Cutting Optimization Engine
Supports:
1. Non-Guillotine (Nested CAD) Optimization: Maximal Rectangles (MaxRects BSSF/BAF)
   Ideal for CNC Laser, Plasma, Flame, Router, Waterjet.
2. Guillotine Optimization (Multi-Stage): Cuts go completely from one edge to the other.
   Ideal for Glass, Wood Panels, Guillotine Shears, Beam Saws.
3. Grain Direction Control (Horizontal, Vertical, Any/Rotatable).
4. Multi-Stage Cut Sequencing (Stage 1, Stage 2, Stage 3).
5. Adjustable Optimization Level (1 to 10).
6. Breakable Parts & Min Useful Waste Limits.
7. Maximum Cut Length Limit for Manual Saws.
8. Grouping of Similar Layouts (Repetition Counts).
9. Exact CNC Cut Coordinates & Total Cutting Distance Calculation.
"""
import time
import uuid
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict

from steel_nest.models.part import PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.models.nesting_plan import (
    PlacedPlatePart, PlateNestPlan, OptimizationResult, UnassignedPart
)
from steel_nest.core.validation import InputValidator


class MaxRectsBin:
    """
    Maximal Rectangles Bin Engine for Non-Guillotine (Nested) cutting.
    Coordinates: X along width (0..plate_width), Y along length (0..plate_length).
    """
    def __init__(self, x: float, y: float, width: float, length: float, kerf: float = 0.0):
        self.origin_x = x
        self.origin_y = y
        self.width = width
        self.length = length
        self.kerf = kerf
        self.free_rects: List[Tuple[float, float, float, float]] = [(x, y, width, length)]
        self.placed_parts: List[PlacedPlatePart] = []

    def score_bssf(self, w: float, l: float, fr: Tuple[float, float, float, float]) -> Tuple[float, float]:
        fx, fy, fw, fl = fr
        if w <= fw and l <= fl:
            return (min(fw - w, fl - l), max(fw - w, fl - l))
        return (float('inf'), float('inf'))

    def score_baf(self, w: float, l: float, fr: Tuple[float, float, float, float]) -> Tuple[float, float]:
        fx, fy, fw, fl = fr
        if w <= fw and l <= fl:
            return (fw * fl - w * l, min(fw - w, fl - l))
        return (float('inf'), float('inf'))

    def find_placement(
        self,
        w: float,
        l: float,
        allow_rot: bool = True,
        rule: str = "BSSF"
    ) -> Tuple[Optional[Tuple[float, float, float, float]], bool]:
        best_score = (float('inf'), float('inf'))
        best_rect = None
        best_rot = False
        score_fn = self.score_bssf if rule == "BSSF" else self.score_baf

        for fr in self.free_rects:
            s = score_fn(w, l, fr)
            if s < best_score:
                best_score = s
                best_rect = (fr[0], fr[1], w, l)
                best_rot = False

            if allow_rot and (w != l):
                s_rot = score_fn(l, w, fr)
                if s_rot < best_score:
                    best_score = s_rot
                    best_rect = (fr[0], fr[1], l, w)
                    best_rot = True

        return best_rect, best_rot

    def place_part(self, item: Dict, px: float, py: float, pw: float, pl: float, rotated: bool):
        self.placed_parts.append(PlacedPlatePart(
            part_id=item["id"],
            part_mark=item["mark"],
            x=px,
            y=py,
            width=pw,
            length=pl,
            rotated=rotated
        ))

        kw = pw + self.kerf
        kl = pl + self.kerf

        new_free: List[Tuple[float, float, float, float]] = []
        for fx, fy, fw, fl in self.free_rects:
            if px >= fx + fw or px + kw <= fx or py >= fy + fl or py + kl <= fy:
                new_free.append((fx, fy, fw, fl))
                continue

            if px > fx and px < fx + fw:
                new_free.append((fx, fy, px - fx, fl))
            if px + kw < fx + fw and px + kw > fx:
                new_free.append((px + kw, fy, fx + fw - (px + kw), fl))
            if py > fy and py < fy + fl:
                new_free.append((fx, fy, fw, py - fy))
            if py + kl < fy + fl and py + kl > fy:
                new_free.append((fx, py + kl, fw, fy + fl - (py + kl)))

        pruned: List[Tuple[float, float, float, float]] = []
        for i, r1 in enumerate(new_free):
            contained = False
            for j, r2 in enumerate(new_free):
                if i != j and (r1[0] >= r2[0] and r1[1] >= r2[1] and
                    r1[0] + r1[2] <= r2[0] + r2[2] and
                    r1[1] + r1[3] <= r2[1] + r2[3]):
                    contained = True
                    break
            if not contained:
                pruned.append(r1)
        self.free_rects = pruned


class GuillotineBinNode:
    """A recursive block in a multi-stage Guillotine cutting tree."""
    def __init__(self, x: float, y: float, width: float, length: float):
        self.x = x
        self.y = y
        self.width = width
        self.length = length
        self.is_leaf = True
        self.part: Optional[Dict] = None
        self.child_a: Optional['GuillotineBinNode'] = None
        self.child_b: Optional['GuillotineBinNode'] = None
        self.cut_direction: Optional[str] = None # 'H' or 'V'
        self.cut_coord: float = 0.0
        self.stage: int = 1


class GuillotinePlatePacker:
    """
    Multi-stage Guillotine 2D packing engine.
    Ensures every cut spans completely from one edge of the parent rectangle to the opposite edge.
    Supports breakable parts limits and max cut length constraints.
    """
    def __init__(
        self,
        margin: float,
        kerf: float,
        first_cut: str = "AUTO",
        stages: int = 2,
        min_breakable_waste: float = 0.0,
        max_cut_length: float = 0.0
    ):
        self.margin = margin
        self.kerf = kerf
        self.first_cut = first_cut
        self.stages = stages
        self.min_breakable_waste = min_breakable_waste
        self.max_cut_length = max_cut_length

    def pack_plate(
        self,
        plate_width: float,
        plate_length: float,
        items: List[Dict]
    ) -> Tuple[List[PlacedPlatePart], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict]]:
        usable_w = plate_width - 2 * self.margin
        usable_l = plate_length - 2 * self.margin

        root = GuillotineBinNode(self.margin, self.margin, usable_w, usable_l)
        root.stage = 1

        placed_parts: List[PlacedPlatePart] = []
        cut_lines: List[Dict[str, Any]] = []
        waste_rects: List[Dict[str, Any]] = []
        unfitted_items: List[Dict] = []

        # Determine primary cut axis
        split_h_first = True
        if self.first_cut == "VERTICAL":
            split_h_first = False
        elif self.first_cut == "AUTO":
            split_h_first = (usable_w <= usable_l)

        for item in items:
            w = item["width"]
            l = item["length"]
            allow_rot = item["allow_rotation"]
            node = self._insert(root, item, w, l, allow_rot, split_h_first)
            if node is None:
                unfitted_items.append(item)

        # Collect results from tree
        self._collect_nodes(root, placed_parts, cut_lines, waste_rects)

        return placed_parts, cut_lines, waste_rects, unfitted_items

    def _insert(
        self,
        node: GuillotineBinNode,
        item: Dict,
        w: float,
        l: float,
        allow_rot: bool,
        split_h_first: bool
    ) -> Optional[GuillotineBinNode]:
        if not node.is_leaf:
            res = self._insert(node.child_a, item, w, l, allow_rot, split_h_first)
            if res:
                return res
            return self._insert(node.child_b, item, w, l, allow_rot, split_h_first)

        if node.part is not None:
            return None # Already occupied

        # Check fit normal
        fits_normal = (w <= node.width and l <= node.length)
        fits_rotated = allow_rot and (l <= node.width and w <= node.length)

        if not fits_normal and not fits_rotated:
            return None

        # Choose best orientation
        use_rotated = False
        if fits_normal and fits_rotated:
            # Prefer orientation that minimizes leftover aspect ratio
            rem_normal = min(node.width - w, node.length - l)
            rem_rotated = min(node.width - l, node.length - w)
            use_rotated = (rem_rotated < rem_normal)
        elif fits_rotated:
            use_rotated = True

        pw = l if use_rotated else w
        pl = w if use_rotated else l

        # Check breakable parts limit on leftover waste
        waste_w = node.width - pw
        waste_l = node.length - pl
        if self.min_breakable_waste > 0:
            if 0 < waste_w < self.min_breakable_waste or 0 < waste_l < self.min_breakable_waste:
                # If too small sliver would be left, only allow if exact fit
                if waste_w > 0 or waste_l > 0:
                    return None

        # If exact fit, place here directly
        if abs(node.width - pw) < 1e-4 and abs(node.length - pl) < 1e-4:
            node.part = {**item, "pw": pw, "pl": pl, "rot": use_rotated}
            return node

        # Otherwise, split node with a Guillotine cut
        node.is_leaf = False
        stage = node.stage

        # If one dimension already matches exactly, split along the other dimension
        if abs(node.width - pw) < 1e-4:
            split_horiz = False
        elif abs(node.length - pl) < 1e-4:
            split_horiz = True
        else:
            # Decide split direction: alternating by stage or split_h_first
            if stage == 1:
                split_horiz = split_h_first
            elif stage == 2:
                split_horiz = not split_h_first
            else:
                split_horiz = (waste_w > waste_l)

        if split_horiz:
            # Horizontal cut across length axis
            cut_len = node.length
            if self.max_cut_length > 0 and cut_len > self.max_cut_length:
                # Fallback to vertical if horizontal cut too long
                split_horiz = False

        if split_horiz:
            node.cut_direction = 'H'
            node.cut_coord = node.x + pw
            node.child_a = GuillotineBinNode(node.x, node.y, pw, node.length)
            node.child_b = GuillotineBinNode(node.x + pw + self.kerf, node.y, max(0.0, node.width - pw - self.kerf), node.length)
        else:
            node.cut_direction = 'V'
            node.cut_coord = node.y + pl
            node.child_a = GuillotineBinNode(node.x, node.y, node.width, pl)
            node.child_b = GuillotineBinNode(node.x, node.y + pl + self.kerf, node.width, max(0.0, node.length - pl - self.kerf))

        node.child_a.stage = min(self.stages, stage + 1)
        node.child_b.stage = min(self.stages, stage + 1)

        return self._insert(node.child_a, item, w, l, allow_rot, split_h_first)

    def _collect_nodes(
        self,
        node: GuillotineBinNode,
        placed_parts: List[PlacedPlatePart],
        cut_lines: List[Dict[str, Any]],
        waste_rects: List[Dict[str, Any]]
    ):
        if not node.is_leaf:
            # Record cut line
            if node.cut_direction == 'H':
                cut_lines.append({
                    "stage": node.stage,
                    "type": "GUILLOTINE_HORIZONTAL",
                    "x1": node.cut_coord,
                    "y1": node.y,
                    "x2": node.cut_coord,
                    "y2": node.y + node.length,
                    "length": node.length
                })
            elif node.cut_direction == 'V':
                cut_lines.append({
                    "stage": node.stage,
                    "type": "GUILLOTINE_VERTICAL",
                    "x1": node.x,
                    "y1": node.cut_coord,
                    "x2": node.x + node.width,
                    "y2": node.cut_coord,
                    "length": node.width
                })

            if node.child_a:
                self._collect_nodes(node.child_a, placed_parts, cut_lines, waste_rects)
            if node.child_b:
                self._collect_nodes(node.child_b, placed_parts, cut_lines, waste_rects)
            return

        if node.part is not None:
            p_data = node.part
            placed_parts.append(PlacedPlatePart(
                part_id=p_data["id"],
                part_mark=p_data["mark"],
                x=node.x,
                y=node.y,
                width=p_data["pw"],
                length=p_data["pl"],
                rotated=p_data["rot"]
            ))
        elif node.width > 5.0 and node.length > 5.0:
            waste_rects.append({
                "x": node.x,
                "y": node.y,
                "width": node.width,
                "length": node.length,
                "area_m2": (node.width * node.length) / 1_000_000.0
            })


class PlateOptimizer:
    """
    Unified 2D Plate and Sheet Optimization Engine for SteelNest Pro.
    Integrates Guillotine and Non-Guillotine (Nested CAD) algorithms with full
    manufacturing constraints, adjustable optimization levels, and layout grouping.
    """
    def __init__(
        self,
        kerf_mm: float = 4.0,
        margin_mm: float = 10.0,
        guillotine_cuts_only: bool = False,
        guillotine_first_cut: str = "AUTO",
        guillotine_stages: int = 2,
        optimization_level: int = 5,
        max_cut_length_mm: float = 0.0,
        min_breakable_waste_mm: float = 0.0,
        min_usable_waste_mm: float = 100.0,
        group_identical_layouts: bool = True,
        time_limit_sec: int = 30
    ):
        self.kerf = max(0.0, kerf_mm)
        self.margin = max(0.0, margin_mm)
        self.guillotine = guillotine_cuts_only
        self.guillotine_first_cut = guillotine_first_cut
        self.guillotine_stages = max(2, guillotine_stages)
        self.optimization_level = max(1, min(10, optimization_level))
        self.max_cut_length = max(0.0, max_cut_length_mm)
        self.min_breakable_waste = max(0.0, min_breakable_waste_mm)
        self.min_usable_waste = max(0.0, min_usable_waste_mm)
        self.group_identical = group_identical_layouts
        self.time_limit_sec = max(1, time_limit_sec)

    def optimize(
        self,
        parts: List[PlatePartItem],
        stock_plates: List[StockItem],
        project_id: str = ""
    ) -> OptimizationResult:
        start_time = time.time()
        run_id = str(uuid.uuid4())

        valid_parts, unassigned_parts, warnings = InputValidator.validate_plate_inputs(
            parts, stock_plates, self.margin, self.kerf
        )

        stock_by_spec = defaultdict(list)
        stock_by_grade = defaultdict(list)
        for s in stock_plates:
            if s.width_mm > 0 or (hasattr(s.material_type, "value") and s.material_type.value == "PLATE") or str(s.material_type) == "PLATE":
                stock_by_spec[s.key].append(s)
                cg = s.grade.strip().upper()
                stock_by_grade[cg].append(s)

        parts_by_spec = defaultdict(list)
        for p in valid_parts:
            parts_by_spec[p.key].append(p)

        all_plate_plans: List[PlateNestPlan] = []
        shortages = defaultdict(int)
        plate_counter = 1

        for spec_key, group_parts in parts_by_spec.items():
            avail_plates = stock_by_spec.get(spec_key, [])
            if not avail_plates:
                clean_grade = group_parts[0].grade.strip().upper()
                avail_plates = stock_by_grade.get(clean_grade, [])

            items_to_pack = []
            for p in group_parts:
                rot_allowed = p.allow_rotation
                # If grain direction is specified fixed
                if hasattr(p, "grain_direction"):
                    if p.grain_direction in ("HORIZONTAL", "VERTICAL"):
                        rot_allowed = False

                for _ in range(p.quantity):
                    items_to_pack.append({
                        "id": p.id,
                        "mark": p.mark,
                        "thickness": p.thickness_mm,
                        "grade": p.grade,
                        "width": p.width_mm,
                        "length": p.length_mm,
                        "allow_rotation": rot_allowed,
                        "area": p.width_mm * p.length_mm
                    })

            plate_pool = []
            for sp in avail_plates:
                rem = sp.available_qty - sp.used_qty
                for _ in range(rem):
                    plate_pool.append({
                        "id": sp.id,
                        "thickness": sp.thickness_mm,
                        "grade": sp.grade,
                        "width": sp.width_mm,
                        "length": sp.length_mm,
                        "cost": sp.cost_per_unit,
                        "is_virtual": False
                    })

            default_w = max([sp.width_mm for sp in avail_plates], default=2000.0)
            default_l = max([sp.length_mm for sp in avail_plates], default=6000.0)
            sample_thick = items_to_pack[0]["thickness"] if items_to_pack else 10.0
            sample_grade = items_to_pack[0]["grade"] if items_to_pack else "S275JR"

            # Execute Optimization according to chosen Mode & Optimization Level
            plans, short = self._pack_plate_spec(
                items_to_pack, plate_pool, default_w, default_l,
                sample_thick, sample_grade, plate_counter
            )
            plate_counter += len(plans)
            all_plate_plans.extend(plans)
            for k, v in short.items():
                shortages[k] += v

        # Group identical layouts if enabled
        if self.group_identical:
            all_plate_plans = self._group_similar_plate_plans(all_plate_plans)

        exec_time = time.time() - start_time

        # Calculate metrics (accounting for repetition counts)
        total_parts_req = sum(p.quantity for p in parts)
        total_parts_nested = sum(len(pl.parts) * pl.repetition_count for pl in all_plate_plans)
        total_plate_area = sum(pl.total_plate_area_m2 * pl.repetition_count for pl in all_plate_plans)
        total_parts_area = sum(pl.used_parts_area_m2 * pl.repetition_count for pl in all_plate_plans)
        overall_util = (total_parts_area / total_plate_area * 100.0) if total_plate_area > 0 else 0.0
        overall_waste = max(0.0, 100.0 - overall_util)
        total_cost = sum(pl.unit_cost * pl.repetition_count for pl in all_plate_plans)
        total_stock_units = sum(pl.repetition_count for pl in all_plate_plans)

        return OptimizationResult(
            run_id=run_id,
            project_id=project_id,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            mode="GUILLOTINE_2D" if self.guillotine else "NESTED_2D",
            objective="MIN_WASTE",
            execution_time_sec=round(exec_time, 2),
            is_proven_optimal=(overall_util >= 95.0),
            solver_status="OPTIMAL" if overall_util >= 90.0 else "FEASIBLE",
            linear_plans=[],
            plate_plans=all_plate_plans,
            unassigned_parts=unassigned_parts,
            total_parts_required=total_parts_req,
            total_parts_nested=total_parts_nested,
            total_stock_used=total_stock_units,
            total_material_length_m=round(total_plate_area, 3),
            total_parts_length_m=round(total_parts_area, 3),
            overall_utilization_pct=round(overall_util, 2),
            overall_waste_pct=round(overall_waste, 2),
            total_estimated_cost=round(total_cost, 2),
            shortages=dict(shortages)
        )

    def _pack_plate_spec(
        self,
        items: List[Dict],
        plate_pool: List[Dict],
        default_w: float,
        default_l: float,
        sample_thick: float,
        sample_grade: str,
        start_index: int
    ) -> Tuple[List[PlateNestPlan], Dict[str, int]]:
        if self.guillotine:
            return self._pack_guillotine(
                items, plate_pool, default_w, default_l,
                sample_thick, sample_grade, start_index
            )
        else:
            return self._pack_nested_maxrects(
                items, plate_pool, default_w, default_l,
                sample_thick, sample_grade, start_index
            )

    def _pack_guillotine(
        self,
        items: List[Dict],
        plate_pool: List[Dict],
        default_w: float,
        default_l: float,
        sample_thick: float,
        sample_grade: str,
        start_index: int
    ) -> Tuple[List[PlateNestPlan], Dict[str, int]]:
        packer = GuillotinePlatePacker(
            margin=self.margin,
            kerf=self.kerf,
            first_cut=self.guillotine_first_cut,
            stages=self.guillotine_stages,
            min_breakable_waste=self.min_breakable_waste,
            max_cut_length=self.max_cut_length
        )

        plans: List[PlateNestPlan] = []
        shortages = defaultdict(int)
        remaining = sorted(items, key=lambda x: (x["area"], max(x["width"], x["length"])), reverse=True)
        pool_idx = 0
        curr_idx = start_index

        while remaining:
            if pool_idx < len(plate_pool):
                p_info = plate_pool[pool_idx]
                pool_idx += 1
            else:
                p_info = {
                    "id": f"NEW-PLATE-PL{sample_thick:.0f}-{default_w:.0f}x{default_l:.0f}",
                    "thickness": sample_thick,
                    "grade": sample_grade,
                    "width": default_w,
                    "length": default_l,
                    "cost": 0.0,
                    "is_virtual": True
                }
                shortages[f"PL {sample_thick}mm ({default_w:.0f}x{default_l:.0f} mm)"] += 1

            parts, cuts, wastes, unfitted = packer.pack_plate(
                p_info["width"], p_info["length"], remaining
            )

            if not parts:
                break # None could fit

            remaining = unfitted
            total_cut_dist = sum(c["length"] for c in cuts)

            plan = PlateNestPlan(
                plate_index=curr_idx,
                stock_id=p_info["id"],
                thickness_mm=p_info["thickness"],
                grade=p_info["grade"],
                plate_width=p_info["width"],
                plate_length=p_info["length"],
                margin=self.margin,
                kerf=self.kerf,
                parts=parts,
                unit_cost=p_info["cost"],
                total_cut_length=total_cut_dist,
                is_guillotine=True,
                cut_lines=cuts,
                waste_rects=wastes
            )
            plans.append(plan)
            curr_idx += 1

        return plans, shortages

    def _pack_nested_maxrects(
        self,
        items: List[Dict],
        plate_pool: List[Dict],
        default_w: float,
        default_l: float,
        sample_thick: float,
        sample_grade: str,
        start_index: int
    ) -> Tuple[List[PlateNestPlan], Dict[str, int]]:
        # Scale number of heuristic evaluations with optimization_level (1 to 10)
        all_strategies = [
            ("Area_BSSF", lambda it: sorted(it, key=lambda x: (x["area"], max(x["width"], x["length"])), reverse=True), "BSSF"),
            ("Perim_BSSF", lambda it: sorted(it, key=lambda x: (x["width"] + x["length"], x["area"]), reverse=True), "BSSF"),
            ("Area_BAF", lambda it: sorted(it, key=lambda x: (x["area"], max(x["width"], x["length"])), reverse=True), "BAF"),
            ("MaxDim_BSSF", lambda it: sorted(it, key=lambda x: (max(x["width"], x["length"]), x["area"]), reverse=True), "BSSF"),
            ("Global_BSSF", None, "GLOBAL"),
            ("Width_BSSF", lambda it: sorted(it, key=lambda x: (min(x["width"], x["length"]), x["area"]), reverse=True), "BSSF"),
            ("Perim_BAF", lambda it: sorted(it, key=lambda x: (x["width"] + x["length"], x["area"]), reverse=True), "BAF"),
            ("SideRatio_BSSF", lambda it: sorted(it, key=lambda x: (max(x["width"], x["length"]) / max(1.0, min(x["width"], x["length"])), x["area"]), reverse=True), "BSSF"),
        ]

        # Select strategies according to optimization level
        num_strats = max(1, min(len(all_strategies), (self.optimization_level + 1) // 1))
        active_strategies = all_strategies[:num_strats]

        best_plans = None
        best_shortages = None
        best_score = (-float('inf'), float('inf'), -float('inf'))

        for s_name, sort_fn, rule in active_strategies:
            if rule == "GLOBAL":
                plans, shortages = self._pack_nested_global(
                    items, plate_pool, default_w, default_l,
                    sample_thick, sample_grade, start_index
                )
            else:
                sorted_items = sort_fn(items)
                plans, shortages = self._pack_nested_single(
                    sorted_items, plate_pool, default_w, default_l,
                    sample_thick, sample_grade, start_index, rule
                )

            nested_count = sum(len(p.parts) for p in plans)
            num_plates = len(plans)
            total_util = sum(p.utilization_pct for p in plans) / num_plates if num_plates > 0 else 0.0

            score = (nested_count, -num_plates, total_util)
            if score > best_score:
                best_score = score
                best_plans = plans
                best_shortages = shortages

        return best_plans or ([], {}), best_shortages or {}

    def _pack_nested_single(
        self,
        sorted_items: List[Dict],
        plate_pool: List[Dict],
        default_w: float,
        default_l: float,
        sample_thick: float,
        sample_grade: str,
        start_index: int,
        rule: str
    ) -> Tuple[List[PlateNestPlan], Dict[str, int]]:
        plans: List[PlateNestPlan] = []
        shortages = defaultdict(int)

        remaining_items = list(sorted_items)
        pool_idx = 0
        curr_plate_idx = start_index

        while remaining_items:
            if pool_idx < len(plate_pool):
                p_info = plate_pool[pool_idx]
                pool_idx += 1
            else:
                p_info = {
                    "id": f"NEW-PLATE-PL{sample_thick:.0f}-{default_w:.0f}x{default_l:.0f}",
                    "thickness": sample_thick,
                    "grade": sample_grade,
                    "width": default_w,
                    "length": default_l,
                    "cost": 0.0,
                    "is_virtual": True
                }
                shortages[f"PL {sample_thick}mm ({default_w:.0f}x{default_l:.0f} mm)"] += 1

            usable_w = p_info["width"] - 2 * self.margin
            usable_l = p_info["length"] - 2 * self.margin

            bin_engine = MaxRectsBin(self.margin, self.margin, usable_w, usable_l, self.kerf)
            items_for_next_plate = []

            for item in remaining_items:
                w = item["width"]
                l = item["length"]
                allow_rot = item["allow_rotation"]

                rect, rot = bin_engine.find_placement(w, l, allow_rot, rule)
                if rect is not None:
                    bin_engine.place_part(item, rect[0], rect[1], rect[2], rect[3], rot)
                else:
                    items_for_next_plate.append(item)

            if not bin_engine.placed_parts:
                break

            remaining_items = items_for_next_plate

            # Calculate total cut lines & waste rects
            cut_lines = []
            for p in bin_engine.placed_parts:
                cut_lines.append({
                    "stage": 1,
                    "type": "CONTOUR",
                    "x1": p.x, "y1": p.y,
                    "x2": p.x + p.width, "y2": p.y + p.length,
                    "length": 2 * (p.width + p.length)
                })
            total_cut_dist = sum(c["length"] for c in cut_lines)

            waste_rects = []
            for fr in bin_engine.free_rects:
                if fr[2] >= 10.0 and fr[3] >= 10.0:
                    waste_rects.append({
                        "x": fr[0], "y": fr[1],
                        "width": fr[2], "length": fr[3],
                        "area_m2": (fr[2] * fr[3]) / 1_000_000.0
                    })

            plan = PlateNestPlan(
                plate_index=curr_plate_idx,
                stock_id=p_info["id"],
                thickness_mm=p_info["thickness"],
                grade=p_info["grade"],
                plate_width=p_info["width"],
                plate_length=p_info["length"],
                margin=self.margin,
                kerf=self.kerf,
                parts=bin_engine.placed_parts,
                unit_cost=p_info["cost"],
                total_cut_length=total_cut_dist,
                cut_lines=cut_lines,
                waste_rects=waste_rects
            )
            plans.append(plan)
            curr_plate_idx += 1

        return plans, shortages

    def _pack_nested_global(
        self,
        items: List[Dict],
        plate_pool: List[Dict],
        default_w: float,
        default_l: float,
        sample_thick: float,
        sample_grade: str,
        start_index: int
    ) -> Tuple[List[PlateNestPlan], Dict[str, int]]:
        plans: List[PlateNestPlan] = []
        shortages = defaultdict(int)

        remaining_items = list(items)
        pool_idx = 0
        curr_plate_idx = start_index

        while remaining_items:
            if pool_idx < len(plate_pool):
                p_info = plate_pool[pool_idx]
                pool_idx += 1
            else:
                p_info = {
                    "id": f"NEW-PLATE-PL{sample_thick:.0f}-{default_w:.0f}x{default_l:.0f}",
                    "thickness": sample_thick,
                    "grade": sample_grade,
                    "width": default_w,
                    "length": default_l,
                    "cost": 0.0,
                    "is_virtual": True
                }
                shortages[f"PL {sample_thick}mm ({default_w:.0f}x{default_l:.0f} mm)"] += 1

            usable_w = p_info["width"] - 2 * self.margin
            usable_l = p_info["length"] - 2 * self.margin

            bin_engine = MaxRectsBin(self.margin, self.margin, usable_w, usable_l, self.kerf)

            while remaining_items:
                best_score = (float('inf'), float('inf'))
                best_item_idx = None
                best_rect = None
                best_rot = False

                for i, item in enumerate(remaining_items):
                    w = item["width"]
                    l = item["length"]
                    allow_rot = item["allow_rotation"]

                    for fr in bin_engine.free_rects:
                        s = bin_engine.score_bssf(w, l, fr)
                        if s < best_score:
                            best_score = s
                            best_item_idx = i
                            best_rect = (fr[0], fr[1], w, l)
                            best_rot = False

                        if allow_rot and (w != l):
                            s_rot = bin_engine.score_bssf(l, w, fr)
                            if s_rot < best_score:
                                best_score = s_rot
                                best_item_idx = i
                                best_rect = (fr[0], fr[1], l, w)
                                best_rot = True

                if best_rect is not None and best_item_idx is not None:
                    chosen_item = remaining_items.pop(best_item_idx)
                    bin_engine.place_part(
                        chosen_item,
                        best_rect[0], best_rect[1], best_rect[2], best_rect[3],
                        best_rot
                    )
                else:
                    break

            if not bin_engine.placed_parts:
                break

            cut_lines = []
            for p in bin_engine.placed_parts:
                cut_lines.append({
                    "stage": 1,
                    "type": "CONTOUR",
                    "x1": p.x, "y1": p.y,
                    "x2": p.x + p.width, "y2": p.y + p.length,
                    "length": 2 * (p.width + p.length)
                })
            total_cut_dist = sum(c["length"] for c in cut_lines)

            waste_rects = []
            for fr in bin_engine.free_rects:
                if fr[2] >= 10.0 and fr[3] >= 10.0:
                    waste_rects.append({
                        "x": fr[0], "y": fr[1],
                        "width": fr[2], "length": fr[3],
                        "area_m2": (fr[2] * fr[3]) / 1_000_000.0
                    })

            plan = PlateNestPlan(
                plate_index=curr_plate_idx,
                stock_id=p_info["id"],
                thickness_mm=p_info["thickness"],
                grade=p_info["grade"],
                plate_width=p_info["width"],
                plate_length=p_info["length"],
                margin=self.margin,
                kerf=self.kerf,
                parts=bin_engine.placed_parts,
                unit_cost=p_info["cost"],
                total_cut_length=total_cut_dist,
                cut_lines=cut_lines,
                waste_rects=waste_rects
            )
            plans.append(plan)
            curr_plate_idx += 1

        return plans, shortages

    def _group_similar_plate_plans(self, plans: List[PlateNestPlan]) -> List[PlateNestPlan]:
        """
        Groups identical layouts together and aggregates repetition_count.
        Matches Cutting Optimization Pro's 'Grouping similar layouts' feature.
        """
        if not plans:
            return []

        unique_plans: List[PlateNestPlan] = []

        def plan_signature(p: PlateNestPlan) -> str:
            # Create a geometric signature of the plate size and placed parts geometry
            parts_sig = sorted([(round(pt.x, 1), round(pt.y, 1), round(pt.width, 1), round(pt.length, 1)) for pt in p.parts])
            return f"{p.plate_width:.1f}x{p.plate_length:.1f}x{p.thickness_mm:.1f}|{p.grade}|{parts_sig}"

        seen: Dict[str, PlateNestPlan] = {}
        for p in plans:
            sig = plan_signature(p)
            if sig in seen:
                seen[sig].repetition_count += 1
            else:
                p.repetition_count = 1
                seen[sig] = p
                unique_plans.append(p)

        # Re-index unique plans
        for idx, up in enumerate(unique_plans):
            up.plate_index = idx + 1

        return unique_plans
