"""
1D Linear Cutting Stock Optimization Engine
Supports Mode 1 (Free Nesting), Mode 2 (Single Cut), and Mode 3 (Double Cut)
with OR-Tools CP-SAT Solver and Best-Fit-Decreasing Heuristic.
"""
import time
import uuid
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from ortools.sat.python import cp_model

from steel_nest.config import LinearOptimizationMode, NestingObjective, RemnantStatus
from steel_nest.models.part import PartCutItem
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.nesting_plan import (
    CutSegment, LinearBarPlan, OptimizationResult, UnassignedPart
)
from steel_nest.core.validation import InputValidator

class LinearOptimizer:
    def __init__(
        self,
        mode: LinearOptimizationMode = LinearOptimizationMode.FREE_NESTING,
        objective: NestingObjective = NestingObjective.MIN_WASTE,
        kerf_mm: float = 3.0,
        trim_start_mm: float = 15.0,
        trim_end_mm: float = 15.0,
        min_remnant_length_mm: float = 500.0,
        time_limit_sec: int = 30,
        allow_remnants_use: bool = True,
        group_identical_layouts: bool = True
    ):
        self.mode = mode
        self.objective = objective
        self.kerf = max(0.0, kerf_mm)
        self.trim_start = max(0.0, trim_start_mm)
        self.trim_end = max(0.0, trim_end_mm)
        self.total_trim = self.trim_start + self.trim_end
        self.min_remnant = max(0.0, min_remnant_length_mm)
        self.time_limit_sec = max(1, time_limit_sec)
        self.allow_remnants_use = allow_remnants_use
        self.group_identical = group_identical_layouts

    @staticmethod
    def _group_similar_linear_plans(plans: List[LinearBarPlan]) -> List[LinearBarPlan]:
        """
        Groups identical linear cutting patterns into a single plan with repetition_count.
        Greatly accelerates GUI rendering, tab generation, and memory efficiency.
        """
        if not plans:
            return []

        grouped: List[LinearBarPlan] = []
        for plan in plans:
            matched = False
            plan_cuts = tuple(round(s.length, 1) for s in plan.segments)
            for g in grouped:
                g_cuts = tuple(round(s.length, 1) for s in g.segments)
                if (
                    round(g.stock_length, 1) == round(plan.stock_length, 1)
                    and g.designation == plan.designation
                    and g.grade == plan.grade
                    and g.stock_id == plan.stock_id
                    and g.is_remnant_stock == plan.is_remnant_stock
                    and g_cuts == plan_cuts
                ):
                    g.repetition_count += getattr(plan, 'repetition_count', 1)
                    matched = True
                    break
            if not matched:
                grouped.append(plan)

        for idx, p in enumerate(grouped):
            p.bar_index = idx + 1

        return grouped

    def optimize(
        self,
        parts: List[PartCutItem],
        stock: List[StockItem],
        project_id: str = ""
    ) -> OptimizationResult:
        start_time = time.time()
        run_id = str(uuid.uuid4())

        # Step 1: Validate inputs
        valid_parts, unassigned_parts, warnings = InputValidator.validate_linear_inputs(
            parts, stock, self.kerf, self.trim_start, self.trim_end
        )

        all_bar_plans: List[LinearBarPlan] = []
        shortages: Dict[str, int] = defaultdict(int)
        is_proven_optimal = True
        overall_status = "OPTIMAL"

        # Step 2: Group by compatible material key (NEVER mix incompatible materials)
        parts_by_key = defaultdict(list)
        for p in valid_parts:
            parts_by_key[p.key].append(p)

        stock_by_key = defaultdict(list)
        for s in stock:
            if s.material_type.value == "LINEAR" if hasattr(s.material_type, "value") else str(s.material_type) == "LINEAR":
                if not self.allow_remnants_use and s.is_remnant:
                    continue
                stock_by_key[s.key].append(s)

        bar_counter = 1

        # Step 3: Optimize per compatible material group
        for mat_key, group_parts in parts_by_key.items():
            avail_stock = stock_by_key.get(mat_key, [])
            
            # Expand parts into individual items
            expanded_items = []
            for p in group_parts:
                for idx in range(p.quantity):
                    expanded_items.append({
                        "part_id": p.id,
                        "part_mark": p.mark,
                        "length": p.length_mm,
                        "weight_kg": p.weight_kg,
                        "designation": p.designation,
                        "grade": p.grade
                    })

            # Sort items in descending order of length
            expanded_items.sort(key=lambda x: x["length"], reverse=True)

            if not expanded_items:
                continue

            # Run specific mode solver
            if self.mode == LinearOptimizationMode.SINGLE_CUT:
                plans, unassigned, short, opt = self._solve_single_cut(
                    expanded_items, avail_stock, bar_counter
                )
            elif self.mode == LinearOptimizationMode.DOUBLE_CUT:
                plans, unassigned, short, opt = self._solve_double_cut(
                    expanded_items, avail_stock, bar_counter
                )
            else: # FREE_NESTING
                plans, unassigned, short, opt = self._solve_free_nesting(
                    expanded_items, avail_stock, bar_counter
                )

            bar_counter += len(plans)
            all_bar_plans.extend(plans)
            unassigned_parts.extend(unassigned)
            for k, count in short.items():
                shortages[k] += count
            if not opt:
                is_proven_optimal = False
                overall_status = "FEASIBLE"

        # Step 4: Group identical cutting patterns
        if getattr(self, 'group_identical', True):
            all_bar_plans = self._group_similar_linear_plans(all_bar_plans)

        exec_time = time.time() - start_time

        # Calculate summary metrics (accounting for repetition counts)
        total_parts_req = sum(p.quantity for p in parts)
        total_parts_nested = sum(len(b.segments) * b.repetition_count for b in all_bar_plans)
        total_material_len = sum(b.stock_length * b.repetition_count for b in all_bar_plans) / 1000.0
        total_parts_len = sum(b.total_part_length * b.repetition_count for b in all_bar_plans) / 1000.0
        
        # Remnants & Waste
        reusable_remnants_len = 0.0
        unusable_waste_len = 0.0
        total_cost = sum(b.unit_cost * b.repetition_count for b in all_bar_plans)

        for b in all_bar_plans:
            rem = b.raw_remnant_length
            if rem >= self.min_remnant:
                reusable_remnants_len += (rem * b.repetition_count) / 1000.0
                unusable_waste_len += ((b.total_trim_length + b.total_kerf_length) * b.repetition_count) / 1000.0
            else:
                unusable_waste_len += ((rem + b.total_trim_length + b.total_kerf_length) * b.repetition_count) / 1000.0

        overall_util = (total_parts_len / total_material_len * 100.0) if total_material_len > 0 else 0.0
        overall_waste = max(0.0, 100.0 - overall_util)

        return OptimizationResult(
            run_id=run_id,
            project_id=project_id,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            mode=self.mode.value,
            objective=self.objective.value,
            execution_time_sec=round(exec_time, 2),
            is_proven_optimal=is_proven_optimal,
            solver_status=overall_status,
            linear_plans=all_bar_plans,
            plate_plans=[],
            unassigned_parts=unassigned_parts,
            total_parts_required=total_parts_req,
            total_parts_nested=total_parts_nested,
            total_stock_used=len(all_bar_plans),
            total_material_length_m=round(total_material_len, 3),
            total_parts_length_m=round(total_parts_len, 3),
            total_reusable_remnants_length_m=round(reusable_remnants_len, 3),
            total_unusable_waste_length_m=round(unusable_waste_len, 3),
            overall_utilization_pct=round(overall_util, 2),
            overall_waste_pct=round(overall_waste, 2),
            total_estimated_cost=round(total_cost, 2),
            shortages=dict(shortages)
        )

    # -------------------------------------------------------------
    # Mode 2: SINGLE CUT LENGTH PER STOCK BAR (Workshop Standard)
    # -------------------------------------------------------------
    def _solve_single_cut(
        self,
        items: List[Dict],
        available_stock: List[StockItem],
        start_bar_index: int
    ) -> Tuple[List[LinearBarPlan], List[UnassignedPart], Dict[str, int], bool]:
        """
        Mode 2: Single Cut Length per Bar (قطعية واحدة بالعود).
        All cut pieces placed on any given stock bar MUST have the EXACT SAME cut length.
        (e.g., cutting 400, 400, 400, ... repeatedly on a 12m bar until exhausted).
        The saw stop is adjusted only once per bar.
        """
        plans: List[LinearBarPlan] = []
        unassigned: List[UnassignedPart] = []
        shortages = defaultdict(int)

        stock_pool = []
        for s in sorted(available_stock, key=lambda x: (x.is_remnant, x.length_mm)):
            rem_qty = min(len(items), s.available_qty - s.used_qty)
            for _ in range(rem_qty):
                stock_pool.append({
                    "id": s.id,
                    "designation": s.designation,
                    "grade": s.grade,
                    "length": s.length_mm,
                    "cost": s.cost_per_unit,
                    "is_remnant": s.is_remnant
                })

        default_stock_len = max([s.length_mm for s in available_stock], default=12000.0)
        sample_desig = items[0]["designation"] if items else "UNKNOWN"
        sample_grade = items[0]["grade"] if items else "S355JR"

        groups_by_len: Dict[float, List[Dict]] = defaultdict(list)
        for it in items:
            groups_by_len[it["length"]].append(it)

        curr_bar_idx = start_bar_index
        used_pool_indices = set()

        for cut_len in sorted(groups_by_len.keys(), reverse=True):
            items_for_len = groups_by_len[cut_len]

            while items_for_len:
                needed_single = cut_len + self.total_trim
                max_avail = max([st["length"] for st in stock_pool], default=default_stock_len)
                if needed_single > max_avail and needed_single > default_stock_len:
                    for it in items_for_len:
                        unassigned.append(UnassignedPart(
                            part_id=it["part_id"],
                            part_mark=it["part_mark"],
                            designation=it["designation"],
                            grade=it["grade"],
                            length=it["length"],
                            reason=f"Part length ({it['length']} mm) exceeds available stock length"
                        ))
                    break

                best_idx = None
                best_fit_count = 0
                best_slack = float('inf')
                best_len = None
                tested_lengths = set()

                for idx, st in enumerate(stock_pool):
                    if idx in used_pool_indices:
                        continue
                    st_len = st["length"]
                    if st_len in tested_lengths:
                        continue
                    tested_lengths.add(st_len)

                    usable = st_len - self.total_trim
                    if usable < cut_len:
                        continue
                    max_fit = int((usable + self.kerf) // (cut_len + self.kerf))
                    if max_fit <= 0:
                        continue
                    pack_n = min(len(items_for_len), max_fit)
                    used_len = pack_n * cut_len + (pack_n - 1) * self.kerf + self.total_trim
                    slack = st_len - used_len
                    if slack >= 0 and slack < best_slack:
                        best_slack = slack
                        best_fit_count = pack_n
                        best_len = st_len

                if best_len is not None:
                    for idx, st in enumerate(stock_pool):
                        if idx not in used_pool_indices and st["length"] == best_len:
                            best_idx = idx
                            break

                if best_idx is not None:
                    used_pool_indices.add(best_idx)
                    st = stock_pool[best_idx]
                    bar_len = st["length"]
                    st_id = st["id"]
                    st_cost = st["cost"]
                    is_rem = st["is_remnant"]
                    pack_qty = best_fit_count
                else:
                    bar_len = default_stock_len
                    st_id = f"NEW-STOCK-{sample_desig}-{default_stock_len:.0f}"
                    st_cost = 0.0
                    is_rem = False
                    usable = bar_len - self.total_trim
                    max_fit = int((usable + self.kerf) // (cut_len + self.kerf))
                    if max_fit <= 0:
                        break
                    pack_qty = min(len(items_for_len), max_fit)
                    shortages[f"{sample_desig} ({default_stock_len:.0f} mm)"] += 1

                packed_items = [items_for_len.pop(0) for _ in range(pack_qty)]

                segments = []
                pos = self.trim_start
                for idx_seg, it in enumerate(packed_items):
                    is_last = (idx_seg == len(packed_items) - 1)
                    k_after = 0.0 if is_last else self.kerf
                    segments.append(CutSegment(
                        part_id=it["part_id"],
                        part_mark=it["part_mark"],
                        start_pos=pos,
                        end_pos=pos + cut_len,
                        length=cut_len,
                        kerf_after=k_after
                    ))
                    pos += cut_len + k_after

                plan = LinearBarPlan(
                    bar_index=curr_bar_idx,
                    stock_id=st_id,
                    designation=packed_items[0]["designation"],
                    grade=packed_items[0]["grade"],
                    stock_length=bar_len,
                    trim_start=self.trim_start,
                    trim_end=self.trim_end,
                    kerf=self.kerf,
                    segments=segments,
                    is_remnant_stock=is_rem,
                    unit_cost=st_cost
                )
                plans.append(plan)
                curr_bar_idx += 1

        return plans, unassigned, shortages, True

    # -------------------------------------------------------------
    # Mode 3: DOUBLE CUT LENGTHS PER STOCK BAR (Workshop Standard)
    # -------------------------------------------------------------
    def _solve_double_cut(
        self,
        items: List[Dict],
        available_stock: List[StockItem],
        start_bar_index: int
    ) -> Tuple[List[LinearBarPlan], List[UnassignedPart], Dict[str, int], bool]:
        """
        Mode 3: Double Cut Lengths per Bar (قطعيتين كحد أقصى بالعود).
        At most TWO DISTINCT cut lengths are allowed per stock bar (e.g. L1 and L2).
        Multiple pieces of L1 and multiple pieces of L2 can be packed together on the same bar
        (e.g., three of 400mm and four of 1200mm). The saw stop is adjusted at most twice per bar.
        """
        plans: List[LinearBarPlan] = []
        unassigned: List[UnassignedPart] = []
        shortages = defaultdict(int)

        stock_pool = []
        for s in sorted(available_stock, key=lambda x: (x.is_remnant, x.length_mm)):
            rem_qty = min(len(items), s.available_qty - s.used_qty)
            for _ in range(rem_qty):
                stock_pool.append({
                    "id": s.id,
                    "designation": s.designation,
                    "grade": s.grade,
                    "length": s.length_mm,
                    "cost": s.cost_per_unit,
                    "is_remnant": s.is_remnant
                })

        default_stock_len = max([s.length_mm for s in available_stock], default=12000.0)
        sample_desig = items[0]["designation"] if items else "UNKNOWN"
        sample_grade = items[0]["grade"] if items else "S355JR"

        available_by_len: Dict[float, List[Dict]] = defaultdict(list)
        for it in items:
            available_by_len[it["length"]].append(it)

        curr_bar_idx = start_bar_index
        used_pool_indices = set()

        while available_by_len:
            L1 = max(available_by_len.keys())
            L1_items = available_by_len[L1]

            needed_single = L1 + self.total_trim
            max_avail = max([st["length"] for i, st in enumerate(stock_pool) if i not in used_pool_indices], default=default_stock_len)
            if needed_single > max_avail and needed_single > default_stock_len:
                for it in L1_items:
                    unassigned.append(UnassignedPart(
                        part_id=it["part_id"],
                        part_mark=it["part_mark"],
                        designation=it["designation"],
                        grade=it["grade"],
                        length=it["length"],
                        reason=f"Part length ({it['length']} mm) exceeds available stock length"
                    ))
                del available_by_len[L1]
                continue

            best_choice = None
            min_slack = float('inf')

            # Test unique bar configurations to avoid redundant combinatorial evaluations
            tested_bar_keys = set()
            candidate_bars = []
            for idx, st in enumerate(stock_pool):
                if idx in used_pool_indices:
                    continue
                b_key = (st["length"], st["is_remnant"])
                if b_key not in tested_bar_keys:
                    tested_bar_keys.add(b_key)
                    candidate_bars.append((st["length"], st["is_remnant"]))

            if not candidate_bars:
                candidate_bars = [(default_stock_len, False)]

            for bar_len, is_rem in candidate_bars:
                usable = bar_len - self.total_trim
                if usable < L1:
                    continue

                max_n1 = min(len(L1_items), int((usable + self.kerf) // (L1 + self.kerf)))
                if max_n1 <= 0:
                    continue

                for n1 in range(max_n1, 0, -1):
                    used_by_L1 = n1 * L1 + (n1 - 1) * self.kerf
                    rem_usable = usable - used_by_L1 - self.kerf

                    slack_a = bar_len - (used_by_L1 + self.total_trim)
                    if slack_a >= 0 and slack_a < min_slack:
                        min_slack = slack_a
                        best_choice = (bar_len, is_rem, n1, None, 0)
                        if slack_a == 0:
                            break

                    if rem_usable > 0:
                        for L2, L2_items in available_by_len.items():
                            if L2 == L1:
                                max_n2_avail = len(L1_items) - n1
                            else:
                                max_n2_avail = len(L2_items)

                            if max_n2_avail <= 0:
                                continue

                            max_n2 = min(max_n2_avail, int((rem_usable + self.kerf) // (L2 + self.kerf)))
                            if max_n2 > 0:
                                tot_parts = n1 + max_n2
                                tot_used = n1 * L1 + max_n2 * L2 + (tot_parts - 1) * self.kerf + self.total_trim
                                slack_b = bar_len - tot_used
                                if slack_b >= 0 and slack_b < min_slack:
                                    min_slack = slack_b
                                    best_choice = (bar_len, is_rem, n1, L2, max_n2)
                                    if slack_b == 0:
                                        break
                if min_slack == 0:
                    break

            if best_choice is None:
                bar_len = default_stock_len
                is_rem = False
                usable = default_stock_len - self.total_trim
                max_n1 = min(len(L1_items), int((usable + self.kerf) // (L1 + self.kerf)))
                if max_n1 <= 0:
                    max_n1 = 1
                best_choice = (bar_len, is_rem, max_n1, None, 0)

            chosen_len, chosen_rem, chosen_n1, chosen_L2, chosen_n2 = best_choice

            st_idx = None
            st_data = None
            for idx, st in enumerate(stock_pool):
                if idx not in used_pool_indices and st["length"] == chosen_len and st["is_remnant"] == chosen_rem:
                    st_idx = idx
                    st_data = st
                    break

            if st_idx is not None:
                used_pool_indices.add(st_idx)
                bar_len = st_data["length"]
                st_id = st_data["id"]
                st_cost = st_data["cost"]
                is_rem = st_data["is_remnant"]
            else:
                bar_len = default_stock_len
                st_id = f"NEW-STOCK-{sample_desig}-{default_stock_len:.0f}"
                st_cost = 0.0
                is_rem = False
                shortages[f"{sample_desig} ({default_stock_len:.0f} mm)"] += 1

            packed_items = [available_by_len[L1].pop(0) for _ in range(chosen_n1)]
            if not available_by_len[L1]:
                del available_by_len[L1]

            if chosen_L2 is not None and chosen_n2 > 0:
                packed_items.extend([available_by_len[chosen_L2].pop(0) for _ in range(chosen_n2)])
                if chosen_L2 in available_by_len and not available_by_len[chosen_L2]:
                    del available_by_len[chosen_L2]

            segments = []
            pos = self.trim_start
            for idx_seg, it in enumerate(packed_items):
                is_last = (idx_seg == len(packed_items) - 1)
                k_after = 0.0 if is_last else self.kerf
                seg_len = it["length"]
                segments.append(CutSegment(
                    part_id=it["part_id"],
                    part_mark=it["part_mark"],
                    start_pos=pos,
                    end_pos=pos + seg_len,
                    length=seg_len,
                    kerf_after=k_after
                ))
                pos += seg_len + k_after

            plan = LinearBarPlan(
                bar_index=curr_bar_idx,
                stock_id=st_id,
                designation=packed_items[0]["designation"],
                grade=packed_items[0]["grade"],
                stock_length=bar_len,
                trim_start=self.trim_start,
                trim_end=self.trim_end,
                kerf=self.kerf,
                segments=segments,
                is_remnant_stock=is_rem,
                unit_cost=st_cost
            )
            plans.append(plan)
            curr_bar_idx += 1

        return plans, unassigned, shortages, True


    # -------------------------------------------------------------
    # Mode 1: FREE NESTING (Minimum Waste - Multiple Cuts per Bar)
    # -------------------------------------------------------------
    def _solve_free_nesting(
        self,
        items: List[Dict],
        available_stock: List[StockItem],
        start_bar_index: int
    ) -> Tuple[List[LinearBarPlan], List[UnassignedPart], Dict[str, int], bool]:
        """
        Solves 1D cutting stock via OR-Tools CP-SAT for exact optimality when feasible,
        with Best-Fit-Decreasing fallback.
        """
        stock_pool = []
        for s in sorted(available_stock, key=lambda x: (x.is_remnant, x.length_mm)):
            rem_qty = min(len(items), s.available_qty - s.used_qty)
            for _ in range(rem_qty):
                stock_pool.append({
                    "id": s.id,
                    "designation": s.designation,
                    "grade": s.grade,
                    "length": s.length_mm,
                    "cost": s.cost_per_unit,
                    "is_remnant": s.is_remnant
                })

        default_stock_len = max([s.length_mm for s in available_stock], default=12000.0)
        sample_desig = items[0]["designation"] if items else "UNKNOWN"
        sample_grade = items[0]["grade"] if items else "S355JR"

        # Try exact CP-SAT solver if problem size is within solver limits
        if len(items) <= 60 and len(stock_pool) <= 30:
            sat_plans, sat_unassigned, sat_short, is_opt = self._solve_free_nesting_cpsat(
                items, stock_pool, default_stock_len, sample_desig, sample_grade, start_bar_index
            )
            if sat_plans is not None:
                return sat_plans, sat_unassigned, sat_short, is_opt

        # Fast constructive heuristic (Best-Fit Decreasing with kerf and trimming)
        return self._solve_free_nesting_bfd(
            items, stock_pool, default_stock_len, sample_desig, sample_grade, start_bar_index
        )

    def _solve_free_nesting_cpsat(
        self,
        items: List[Dict],
        stock_pool: List[Dict],
        default_stock_len: float,
        sample_desig: str,
        sample_grade: str,
        start_bar_index: int
    ) -> Tuple[Optional[List[LinearBarPlan]], List[UnassignedPart], Dict[str, int], bool]:
        """OR-Tools CP-SAT formulation for optimal linear cutting."""
        try:
            model = cp_model.CpModel()
            num_items = len(items)
            
            # Prepare candidate bars (pool + virtual shortage bars)
            candidate_bars = list(stock_pool)
            needed_virtual = max(0, num_items - len(candidate_bars)) + 2
            for v in range(needed_virtual):
                candidate_bars.append({
                    "id": f"NEW-STOCK-{sample_desig}-{default_stock_len:.0f}",
                    "designation": sample_desig,
                    "grade": sample_grade,
                    "length": default_stock_len,
                    "cost": 100.0,
                    "is_remnant": False,
                    "is_virtual": True
                })

            num_bars = len(candidate_bars)
            # x[i, j] = 1 if item i is placed on bar j
            x = {}
            for i in range(num_items):
                for j in range(num_bars):
                    x[i, j] = model.NewBoolVar(f"x_{i}_{j}")

            # y[j] = 1 if bar j is used
            y = [model.NewBoolVar(f"y_{j}") for j in range(num_bars)]

            # count[j] = number of items on bar j
            count = [model.NewIntVar(0, num_items, f"count_{j}") for j in range(num_bars)]
            for j in range(num_bars):
                model.Add(count[j] == sum(x[i, j] for i in range(num_items)))
                # If count[j] >= 1, y[j] = 1
                model.Add(count[j] <= num_items * y[j])
                model.Add(count[j] >= y[j])

            # Each item must be placed on exactly one bar
            for i in range(num_items):
                model.Add(sum(x[i, j] for j in range(num_bars)) == 1)

            # Capacity constraint for each bar:
            # sum(length_i * x_ij) + (count_j - 1)*kerf + total_trim <= stock_length_j
            # When count_j == 0, count_j - 1 is negative, but bounded by y_j
            for j in range(num_bars):
                usable_cap = int(candidate_bars[j]["length"] - self.total_trim)
                # item_sum + kerf * count_j - kerf * y_j <= usable_cap * y_j
                # Multiply lengths by 10 to ensure integer precision
                model.Add(
                    sum(int(items[i]["length"] * 10) * x[i, j] for i in range(num_items))
                    + int(self.kerf * 10) * (count[j] - y[j])
                    <= int(usable_cap * 10) * y[j]
                )

            # Symmetry breaking: prefer earlier bars
            for j in range(num_bars - 1):
                model.Add(y[j] >= y[j + 1])

            # Objective: minimize total stock used / waste
            # Penalize virtual bars more to prioritize physical inventory
            obj_terms = []
            for j in range(num_bars):
                weight = 1000 if candidate_bars[j].get("is_virtual") else 100
                obj_terms.append(weight * y[j])

            model.Minimize(sum(obj_terms))

            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = float(self.time_limit_sec)
            solver.parameters.num_workers = min(2, max(1, os.cpu_count() or 1))
            solver.parameters.max_memory_in_mb = 256.0
            status = solver.Solve(model)

            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                plans: List[LinearBarPlan] = []
                shortages = defaultdict(int)
                curr_idx = start_bar_index

                for j in range(num_bars):
                    if solver.Value(y[j]) == 1:
                        st = candidate_bars[j]
                        bar_items = [items[i] for i in range(num_items) if solver.Value(x[i, j]) == 1]
                        if not bar_items:
                            continue

                        if st.get("is_virtual"):
                            shortages[f"{st['designation']} ({st['length']:.0f} mm)"] += 1

                        # Layout segments
                        segments = []
                        pos = self.trim_start
                        for idx_seg, bi in enumerate(bar_items):
                            is_last = (idx_seg == len(bar_items) - 1)
                            kerf_val = 0.0 if is_last else self.kerf
                            seg = CutSegment(
                                part_id=bi["part_id"],
                                part_mark=bi["part_mark"],
                                start_pos=pos,
                                end_pos=pos + bi["length"],
                                length=bi["length"],
                                kerf_after=kerf_val
                            )
                            segments.append(seg)
                            pos += bi["length"] + kerf_val

                        plan = LinearBarPlan(
                            bar_index=curr_idx,
                            stock_id=st["id"],
                            designation=st["designation"],
                            grade=st["grade"],
                            stock_length=st["length"],
                            trim_start=self.trim_start,
                            trim_end=self.trim_end,
                            kerf=self.kerf,
                            segments=segments,
                            is_remnant_stock=st["is_remnant"],
                            unit_cost=st["cost"]
                        )
                        plans.append(plan)
                        curr_idx += 1

                is_opt = (status == cp_model.OPTIMAL)
                return plans, [], shortages, is_opt
        except Exception:
            pass

        return None, [], {}, False

    def _solve_free_nesting_bfd(
        self,
        items: List[Dict],
        stock_pool: List[Dict],
        default_stock_len: float,
        sample_desig: str,
        sample_grade: str,
        start_bar_index: int
    ) -> Tuple[List[LinearBarPlan], List[UnassignedPart], Dict[str, int], bool]:
        """Best-Fit Decreasing heuristic for linear cutting with kerf and trimming."""
        plans: List[LinearBarPlan] = []
        shortages = defaultdict(int)

        # Active bars being packed: list of dicts with bar info and assigned items
        active_bars: List[Dict] = []
        used_pool_indices = set()

        for item in items:
            req_len = item["length"]
            best_bar_idx = None
            min_remaining_slack = float('inf')

            # Try to place into an existing open bar
            for b_idx, bar in enumerate(active_bars):
                current_used = bar["total_length"]
                # Additional kerf needed if bar already has cuts
                extra_kerf = self.kerf if bar["items"] else 0.0
                new_used = current_used + extra_kerf + req_len
                slack = bar["usable_length"] - new_used
                if slack >= 0 and slack < min_remaining_slack:
                    min_remaining_slack = slack
                    best_bar_idx = b_idx

            if best_bar_idx is not None:
                # Add to existing bar
                bar = active_bars[best_bar_idx]
                if bar["items"]:
                    bar["total_length"] += self.kerf
                bar["total_length"] += req_len
                bar["items"].append(item)
            else:
                # Open a new bar from stock pool or create shortage bar
                best_pool_idx = None
                best_pool_slack = float('inf')
                best_pool_len = None
                tested_pool_lengths = set()

                for p_idx, st in enumerate(stock_pool):
                    if p_idx in used_pool_indices:
                        continue
                    st_len = st["length"]
                    if st_len in tested_pool_lengths:
                        continue
                    tested_pool_lengths.add(st_len)

                    usable = st_len - self.total_trim
                    slack = usable - req_len
                    if slack >= 0 and slack < best_pool_slack:
                        best_pool_slack = slack
                        best_pool_len = st_len

                if best_pool_len is not None:
                    for p_idx, st in enumerate(stock_pool):
                        if p_idx not in used_pool_indices and st["length"] == best_pool_len:
                            best_pool_idx = p_idx
                            break

                if best_pool_idx is not None:
                    used_pool_indices.add(best_pool_idx)
                    st = stock_pool[best_pool_idx]
                    active_bars.append({
                        "stock_id": st["id"],
                        "designation": st["designation"],
                        "grade": st["grade"],
                        "stock_length": st["length"],
                        "usable_length": st["length"] - self.total_trim,
                        "total_length": req_len,
                        "unit_cost": st["cost"],
                        "is_remnant": st["is_remnant"],
                        "items": [item]
                    })
                else:
                    # Allocate shortage bar
                    active_bars.append({
                        "stock_id": f"NEW-STOCK-{sample_desig}-{default_stock_len:.0f}",
                        "designation": sample_desig,
                        "grade": sample_grade,
                        "stock_length": default_stock_len,
                        "usable_length": default_stock_len - self.total_trim,
                        "total_length": req_len,
                        "unit_cost": 0.0,
                        "is_remnant": False,
                        "items": [item]
                    })
                    shortages[f"{sample_desig} ({default_stock_len:.0f} mm)"] += 1

        # Format into LinearBarPlan
        curr_idx = start_bar_index
        for b in active_bars:
            segments = []
            pos = self.trim_start
            for idx_seg, it in enumerate(b["items"]):
                is_last = (idx_seg == len(b["items"]) - 1)
                kerf_val = 0.0 if is_last else self.kerf
                seg = CutSegment(
                    part_id=it["part_id"],
                    part_mark=it["part_mark"],
                    start_pos=pos,
                    end_pos=pos + it["length"],
                    length=it["length"],
                    kerf_after=kerf_val
                )
                segments.append(seg)
                pos += it["length"] + kerf_val

            plan = LinearBarPlan(
                bar_index=curr_idx,
                stock_id=b["stock_id"],
                designation=b["designation"],
                grade=b["grade"],
                stock_length=b["stock_length"],
                trim_start=self.trim_start,
                trim_end=self.trim_end,
                kerf=self.kerf,
                segments=segments,
                is_remnant_stock=b["is_remnant"],
                unit_cost=b["unit_cost"]
            )
            plans.append(plan)
            curr_idx += 1

        return plans, [], shortages, True
