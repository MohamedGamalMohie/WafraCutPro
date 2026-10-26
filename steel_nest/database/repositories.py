"""
Database Repositories for SteelNest Pro
"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from steel_nest.database.db_manager import DatabaseManager
from steel_nest.models.project import Project, ProjectSettings
from steel_nest.models.stock import StockItem, RemnantItem
from steel_nest.models.part import PartCutItem, PlatePartItem
from steel_nest.models.material import SteelProfile
from steel_nest.config import (
    LinearOptimizationMode, NestingObjective, RemnantStatus, MaterialType
)

class ProjectRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, project: Project) -> Project:
        now = datetime.now().isoformat()
        if not project.created_at:
            project.created_at = now
        project.updated_at = now
        
        settings_dict = {
            "kerf_mm": project.settings.kerf_mm,
            "trim_start_mm": project.settings.trim_start_mm,
            "trim_end_mm": project.settings.trim_end_mm,
            "min_remnant_length_mm": project.settings.min_remnant_length_mm,
            "plate_kerf_mm": project.settings.plate_kerf_mm,
            "plate_margin_mm": project.settings.plate_margin_mm,
            "linear_mode": project.settings.linear_mode.value if isinstance(project.settings.linear_mode, LinearOptimizationMode) else str(project.settings.linear_mode),
            "objective": project.settings.objective.value if isinstance(project.settings.objective, NestingObjective) else str(project.settings.objective),
            "time_limit_sec": project.settings.time_limit_sec,
            "allow_remnants_use": project.settings.allow_remnants_use,
            "guillotine_cuts_only": project.settings.guillotine_cuts_only
        }

        with self.db.get_connection() as conn:
            conn.execute("""
            INSERT INTO projects (id, name, code, client, description, created_at, updated_at, settings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id, project.name, project.code, project.client,
                project.description, project.created_at, project.updated_at,
                json.dumps(settings_dict)
            ))
            conn.commit()
        return project

    def get(self, project_id: str) -> Optional[Project]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_project(row)

    def list_all(self) -> List[Project]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [self._row_to_project(r) for r in cursor.fetchall()]

    def update(self, project: Project):
        project.updated_at = datetime.now().isoformat()
        settings_dict = {
            "kerf_mm": project.settings.kerf_mm,
            "trim_start_mm": project.settings.trim_start_mm,
            "trim_end_mm": project.settings.trim_end_mm,
            "min_remnant_length_mm": project.settings.min_remnant_length_mm,
            "plate_kerf_mm": project.settings.plate_kerf_mm,
            "plate_margin_mm": project.settings.plate_margin_mm,
            "linear_mode": project.settings.linear_mode.value if isinstance(project.settings.linear_mode, LinearOptimizationMode) else str(project.settings.linear_mode),
            "objective": project.settings.objective.value if isinstance(project.settings.objective, NestingObjective) else str(project.settings.objective),
            "time_limit_sec": project.settings.time_limit_sec,
            "allow_remnants_use": project.settings.allow_remnants_use,
            "guillotine_cuts_only": project.settings.guillotine_cuts_only
        }
        with self.db.get_connection() as conn:
            conn.execute("""
            UPDATE projects SET name = ?, code = ?, client = ?, description = ?, updated_at = ?, settings_json = ?
            WHERE id = ?
            """, (
                project.name, project.code, project.client, project.description,
                project.updated_at, json.dumps(settings_dict), project.id
            ))
            conn.commit()

    def delete(self, project_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    def duplicate(self, project_id: str, new_name: str, new_code: str) -> Optional[Project]:
        orig = self.get(project_id)
        if not orig:
            return None
        new_proj = Project(
            id=str(uuid.uuid4()),
            name=new_name,
            code=new_code,
            client=orig.client,
            description=f"Copy of {orig.name}: {orig.description}",
            settings=orig.settings
        )
        self.create(new_proj)
        
        # Copy cut lists
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cut_lists_linear WHERE project_id = ?", (project_id,))
            for row in cursor.fetchall():
                conn.execute("""
                INSERT INTO cut_lists_linear (id, project_id, mark, designation, grade, length_mm, quantity, assigned_qty, weight_kg, priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), new_proj.id, row["mark"], row["designation"],
                    row["grade"], row["length_mm"], row["quantity"], row["weight_kg"],
                    row["priority"], row["notes"]
                ))
            cursor.execute("SELECT * FROM cut_lists_plate WHERE project_id = ?", (project_id,))
            for row in cursor.fetchall():
                conn.execute("""
                INSERT INTO cut_lists_plate (id, project_id, mark, thickness_mm, grade, width_mm, length_mm, quantity, assigned_qty, allow_rotation, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """, (
                    str(uuid.uuid4()), new_proj.id, row["mark"], row["thickness_mm"],
                    row["grade"], row["width_mm"], row["length_mm"], row["quantity"],
                    row["allow_rotation"], row["notes"]
                ))
            conn.commit()
        return new_proj

    def _row_to_project(self, row) -> Project:
        settings = ProjectSettings()
        if row["settings_json"]:
            try:
                s = json.loads(row["settings_json"])
                settings.kerf_mm = s.get("kerf_mm", 3.0)
                settings.trim_start_mm = s.get("trim_start_mm", 15.0)
                settings.trim_end_mm = s.get("trim_end_mm", 15.0)
                settings.min_remnant_length_mm = s.get("min_remnant_length_mm", 500.0)
                settings.plate_kerf_mm = s.get("plate_kerf_mm", 4.0)
                settings.plate_margin_mm = s.get("plate_margin_mm", 10.0)
                settings.linear_mode = LinearOptimizationMode(s.get("linear_mode", "FREE_NESTING"))
                settings.objective = NestingObjective(s.get("objective", "MIN_WASTE"))
                settings.time_limit_sec = s.get("time_limit_sec", 30)
                settings.allow_remnants_use = s.get("allow_remnants_use", True)
                settings.guillotine_cuts_only = s.get("guillotine_cuts_only", False)
            except Exception:
                pass
                
        return Project(
            id=row["id"],
            name=row["name"],
            code=row["code"],
            client=row["client"] or "",
            description=row["description"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            settings=settings
        )


class StockRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add(self, stock: StockItem) -> StockItem:
        with self.db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO stock_inventory 
            (id, designation, grade, length_mm, width_mm, thickness_mm, available_qty, used_qty, cost_per_unit, is_remnant, source_project, location, material_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock.id, stock.designation, stock.grade, stock.length_mm, stock.width_mm,
                stock.thickness_mm, stock.available_qty, stock.used_qty, stock.cost_per_unit,
                1 if stock.is_remnant else 0, stock.source_project, stock.location,
                stock.material_type.value if isinstance(stock.material_type, MaterialType) else str(stock.material_type),
                stock.notes
            ))
            conn.commit()
        return stock

    def list_all(self, material_type: Optional[MaterialType] = None) -> List[StockItem]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if material_type:
                cursor.execute("SELECT * FROM stock_inventory WHERE material_type = ? ORDER BY designation, length_mm DESC", (material_type.value,))
            else:
                cursor.execute("SELECT * FROM stock_inventory ORDER BY designation, length_mm DESC")
            return [self._row_to_stock(r) for r in cursor.fetchall()]

    def get_by_key(self, key: str) -> List[StockItem]:
        items = []
        for s in self.list_all():
            if s.key == key:
                items.append(s)
        return items

    def delete(self, stock_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM stock_inventory WHERE id = ?", (stock_id,))
            conn.commit()

    def update_used_qty(self, stock_id: str, added_used: int):
        with self.db.get_connection() as conn:
            conn.execute("UPDATE stock_inventory SET used_qty = used_qty + ? WHERE id = ?", (added_used, stock_id))
            conn.commit()

    def _row_to_stock(self, row) -> StockItem:
        return StockItem(
            id=row["id"],
            designation=row["designation"],
            grade=row["grade"],
            length_mm=row["length_mm"],
            width_mm=row["width_mm"],
            thickness_mm=row["thickness_mm"],
            available_qty=row["available_qty"],
            used_qty=row["used_qty"],
            cost_per_unit=row["cost_per_unit"],
            is_remnant=bool(row["is_remnant"]),
            source_project=row["source_project"] or "",
            location=row["location"] or "Warehouse A",
            material_type=MaterialType(row["material_type"]),
            notes=row["notes"] or ""
        )


class CutListRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_linear(self, item: PartCutItem, project_id: str):
        with self.db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO cut_lists_linear 
            (id, project_id, mark, designation, grade, length_mm, quantity, assigned_qty, weight_kg, priority, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, project_id, item.mark, item.designation, item.grade,
                item.length_mm, item.quantity, item.assigned_qty, item.weight_kg,
                item.priority, item.notes
            ))
            conn.commit()

    def list_linear_by_project(self, project_id: str) -> List[PartCutItem]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cut_lists_linear WHERE project_id = ? ORDER BY mark", (project_id,))
            return [
                PartCutItem(
                    id=r["id"], mark=r["mark"], designation=r["designation"],
                    grade=r["grade"], length_mm=r["length_mm"], quantity=r["quantity"],
                    assigned_qty=r["assigned_qty"], weight_kg=r["weight_kg"],
                    priority=r["priority"], notes=r["notes"] or ""
                )
                for r in cursor.fetchall()
            ]

    def clear_linear(self, project_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM cut_lists_linear WHERE project_id = ?", (project_id,))
            conn.commit()

    def delete_linear(self, item_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM cut_lists_linear WHERE id = ?", (item_id,))
            conn.commit()

    def add_plate(self, item: PlatePartItem, project_id: str):
        with self.db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO cut_lists_plate 
            (id, project_id, mark, thickness_mm, grade, width_mm, length_mm, quantity, assigned_qty, allow_rotation, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, project_id, item.mark, item.thickness_mm, item.grade,
                item.width_mm, item.length_mm, item.quantity, item.assigned_qty,
                1 if item.allow_rotation else 0, item.notes
            ))
            conn.commit()

    def list_plate_by_project(self, project_id: str) -> List[PlatePartItem]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cut_lists_plate WHERE project_id = ? ORDER BY mark", (project_id,))
            return [
                PlatePartItem(
                    id=r["id"], mark=r["mark"], thickness_mm=r["thickness_mm"],
                    grade=r["grade"], width_mm=r["width_mm"], length_mm=r["length_mm"],
                    quantity=r["quantity"], assigned_qty=r["assigned_qty"],
                    allow_rotation=bool(r["allow_rotation"]), notes=r["notes"] or ""
                )
                for r in cursor.fetchall()
            ]

    def clear_plate(self, project_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM cut_lists_plate WHERE project_id = ?", (project_id,))
            conn.commit()

    def delete_plate(self, item_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM cut_lists_plate WHERE id = ?", (item_id,))
            conn.commit()


class RemnantRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add(self, remnant: RemnantItem) -> RemnantItem:
        with self.db.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO remnants 
            (id, original_stock_id, designation, grade, length_mm, width_mm, thickness_mm, material_type, status, created_date, source_project, location, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                remnant.id, remnant.original_stock_id, remnant.designation, remnant.grade,
                remnant.length_mm, remnant.width_mm, remnant.thickness_mm,
                remnant.material_type.value if isinstance(remnant.material_type, MaterialType) else str(remnant.material_type),
                remnant.status.value if isinstance(remnant.status, RemnantStatus) else str(remnant.status),
                remnant.created_date or datetime.now().isoformat(),
                remnant.source_project, remnant.location, remnant.notes
            ))
            conn.commit()
        return remnant

    def list_all(self, status: Optional[RemnantStatus] = None) -> List[RemnantItem]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM remnants WHERE status = ? ORDER BY length_mm DESC", (status.value,))
            else:
                cursor.execute("SELECT * FROM remnants ORDER BY length_mm DESC")
            return [
                RemnantItem(
                    id=r["id"], original_stock_id=r["original_stock_id"],
                    designation=r["designation"], grade=r["grade"],
                    length_mm=r["length_mm"], width_mm=r["width_mm"],
                    thickness_mm=r["thickness_mm"],
                    material_type=MaterialType(r["material_type"]),
                    status=RemnantStatus(r["status"]),
                    created_date=r["created_date"] or "",
                    source_project=r["source_project"] or "",
                    location=r["location"] or "Remnants Rack",
                    notes=r["notes"] or ""
                )
                for r in cursor.fetchall()
            ]

    def update_status(self, remnant_id: str, new_status: RemnantStatus):
        with self.db.get_connection() as conn:
            conn.execute("UPDATE remnants SET status = ? WHERE id = ?", (new_status.value, remnant_id))
            conn.commit()

    def delete(self, remnant_id: str):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM remnants WHERE id = ?", (remnant_id,))
            conn.commit()
