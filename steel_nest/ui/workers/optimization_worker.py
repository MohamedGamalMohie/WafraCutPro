"""
QThread Optimization Worker for Non-blocking Computation
Supports 1D Linear, 2D Plate, and Combined (1D + 2D) simultaneous optimization.
"""
import time
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List

from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.stock import StockItem
from steel_nest.models.nesting_plan import OptimizationResult
from steel_nest.models.project import ProjectSettings
from steel_nest.core.linear_optimizer import LinearOptimizer
from steel_nest.core.plate_optimizer import PlateOptimizer
from steel_nest.config import LinearOptimizationMode

class OptimizationWorker(QThread):
    finished = pyqtSignal(object)       # OptimizationResult
    progress = pyqtSignal(int, str)     # percentage, status message
    error = pyqtSignal(str)

    def __init__(
        self,
        mode_type: str,                 # "LINEAR", "PLATE", or "AUTO"
        settings: ProjectSettings,
        parts_1d: List[PartCutItem],
        parts_2d: List[PlatePartItem],
        stock: List[StockItem],
        project_id: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.mode_type = mode_type
        self.settings = settings
        self.parts_1d = parts_1d
        self.parts_2d = parts_2d
        self.stock = stock
        self.project_id = project_id

    def run(self):
        try:
            start_t = time.time()
            self.progress.emit(10, "فحص المقاسات والكميات والمطابقة...")

            res_1d = None
            res_2d = None

            has_1d = bool(self.parts_1d)
            has_2d = bool(self.parts_2d)

            # Run 1D Linear Nesting if linear parts exist
            if has_1d:
                self.progress.emit(25, f"حساب تقطيع الكمرات والمقاطع ({self.settings.linear_mode.value})...")
                opt_1d = LinearOptimizer(
                    mode=self.settings.linear_mode,
                    objective=self.settings.objective,
                    kerf_mm=self.settings.kerf_mm,
                    trim_start_mm=self.settings.trim_start_mm,
                    trim_end_mm=self.settings.trim_end_mm,
                    min_remnant_length_mm=self.settings.min_remnant_length_mm,
                    time_limit_sec=self.settings.time_limit_sec,
                    allow_remnants_use=self.settings.allow_remnants_use
                )
                res_1d = opt_1d.optimize(self.parts_1d, self.stock, self.project_id)

            # Run 2D Plate Nesting if plate parts exist
            if has_2d:
                self.progress.emit(60, "حساب تفصيل ألواح الصاج مع الدوران وحساب الهالك...")
                opt_2d = PlateOptimizer(
                    kerf_mm=self.settings.plate_kerf_mm,
                    margin_mm=self.settings.plate_margin_mm,
                    guillotine_cuts_only=self.settings.guillotine_cuts_only,
                    guillotine_first_cut=getattr(self.settings, "guillotine_first_cut", "AUTO"),
                    guillotine_stages=getattr(self.settings, "guillotine_stages", 2),
                    optimization_level=getattr(self.settings, "optimization_level", 5),
                    max_cut_length_mm=getattr(self.settings, "max_cut_length_mm", 0.0),
                    min_breakable_waste_mm=getattr(self.settings, "min_breakable_waste_mm", 0.0),
                    min_usable_waste_mm=getattr(self.settings, "min_usable_waste_mm", 100.0),
                    group_identical_layouts=getattr(self.settings, "group_identical_layouts", True),
                    time_limit_sec=self.settings.time_limit_sec
                )
                res_2d = opt_2d.optimize(self.parts_2d, self.stock, self.project_id)

            self.progress.emit(90, "تجميع النتائج والرسوم البيانية وحساب نسب الاستغلال...")

            # Merge results
            if has_1d and not has_2d:
                final_res = res_1d
            elif has_2d and not has_1d:
                final_res = res_2d
            elif has_1d and has_2d:
                # Combined Result
                combined_linear = res_1d.linear_plans if res_1d else []
                combined_plates = res_2d.plate_plans if res_2d else []
                combined_unassigned = (res_1d.unassigned_parts if res_1d else []) + (res_2d.unassigned_parts if res_2d else [])
                combined_shortages = {}
                if res_1d:
                    combined_shortages.update(res_1d.shortages)
                if res_2d:
                    combined_shortages.update(res_2d.shortages)

                tot_req = (res_1d.total_parts_required if res_1d else 0) + (res_2d.total_parts_required if res_2d else 0)
                tot_nested = (res_1d.total_parts_nested if res_1d else 0) + (res_2d.total_parts_nested if res_2d else 0)
                tot_stock = len(combined_linear) + len(combined_plates)

                tot_cost = (res_1d.total_estimated_cost if res_1d else 0.0) + (res_2d.total_estimated_cost if res_2d else 0.0)
                exec_time = time.time() - start_t

                # Overall combined utilization
                util_sum = 0.0
                count_modes = 0
                if res_1d and res_1d.linear_plans:
                    util_sum += res_1d.overall_utilization_pct
                    count_modes += 1
                if res_2d and res_2d.plate_plans:
                    util_sum += res_2d.overall_utilization_pct
                    count_modes += 1
                avg_util = (util_sum / count_modes) if count_modes > 0 else 0.0

                final_res = OptimizationResult(
                    run_id=res_1d.run_id if res_1d else res_2d.run_id,
                    project_id=self.project_id,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                    mode=f"COMBINED (1D: {self.settings.linear_mode.value} + 2D: PLATES)",
                    objective=self.settings.objective.value,
                    execution_time_sec=round(exec_time, 2),
                    is_proven_optimal=res_1d.is_proven_optimal if res_1d else False,
                    solver_status="OPTIMAL" if (res_1d and res_1d.is_proven_optimal) else "FEASIBLE",
                    linear_plans=combined_linear,
                    plate_plans=combined_plates,
                    unassigned_parts=combined_unassigned,
                    total_parts_required=tot_req,
                    total_parts_nested=tot_nested,
                    total_stock_used=tot_stock,
                    total_material_length_m=res_1d.total_material_length_m if res_1d else 0.0,
                    total_parts_length_m=res_1d.total_parts_length_m if res_1d else 0.0,
                    total_reusable_remnants_length_m=res_1d.total_reusable_remnants_length_m if res_1d else 0.0,
                    total_unusable_waste_length_m=res_1d.total_unusable_waste_length_m if res_1d else 0.0,
                    overall_utilization_pct=round(avg_util, 2),
                    overall_waste_pct=round(max(0.0, 100.0 - avg_util), 2),
                    total_estimated_cost=round(tot_cost, 2),
                    shortages=combined_shortages
                )
            else:
                raise ValueError("لا توجد قطع مدخلة للتقطيع!")

            self.progress.emit(100, "تم الانتهاء بنجاح!")
            self.finished.emit(final_res)

        except Exception as e:
            self.error.emit(str(e))
