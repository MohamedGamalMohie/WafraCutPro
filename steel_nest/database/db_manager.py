"""
SQLite Database Manager and Schema Initialization
"""
import os
import sqlite3
import json
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from steel_nest.config import STANDARD_SECTIONS, STANDARD_STEEL_GRADES

DEFAULT_DB_PATH = Path.home() / ".steelnest_pro" / "steelnest_pro.db"

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.home() / ".steelnest_pro"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(DEFAULT_DB_PATH)
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
        self.init_schema()
        self.seed_standard_sections()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Projects Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                client TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                settings_json TEXT
            )
            """)

            # Materials Catalog
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                designation TEXT NOT NULL,
                family TEXT NOT NULL,
                grade TEXT NOT NULL,
                weight_kg_per_m REAL DEFAULT 0.0,
                material_type TEXT DEFAULT 'LINEAR',
                notes TEXT,
                UNIQUE(designation, grade)
            )
            """)

            # Stock Inventory Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_inventory (
                id TEXT PRIMARY KEY,
                designation TEXT NOT NULL,
                grade TEXT NOT NULL,
                length_mm REAL NOT NULL,
                width_mm REAL DEFAULT 0.0,
                thickness_mm REAL DEFAULT 0.0,
                available_qty INTEGER NOT NULL DEFAULT 1,
                used_qty INTEGER NOT NULL DEFAULT 0,
                cost_per_unit REAL DEFAULT 0.0,
                is_remnant INTEGER DEFAULT 0,
                source_project TEXT,
                location TEXT,
                material_type TEXT DEFAULT 'LINEAR',
                notes TEXT
            )
            """)

            # Linear Cut Lists Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cut_lists_linear (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mark TEXT NOT NULL,
                designation TEXT NOT NULL,
                grade TEXT NOT NULL,
                length_mm REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                assigned_qty INTEGER NOT NULL DEFAULT 0,
                weight_kg REAL DEFAULT 0.0,
                priority INTEGER DEFAULT 1,
                notes TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """)

            # Plate Cut Lists Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cut_lists_plate (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mark TEXT NOT NULL,
                thickness_mm REAL NOT NULL,
                grade TEXT NOT NULL,
                width_mm REAL NOT NULL,
                length_mm REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                assigned_qty INTEGER NOT NULL DEFAULT 0,
                allow_rotation INTEGER DEFAULT 1,
                notes TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """)

            # Remnants Inventory Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS remnants (
                id TEXT PRIMARY KEY,
                original_stock_id TEXT,
                designation TEXT NOT NULL,
                grade TEXT NOT NULL,
                length_mm REAL NOT NULL,
                width_mm REAL DEFAULT 0.0,
                thickness_mm REAL DEFAULT 0.0,
                material_type TEXT DEFAULT 'LINEAR',
                status TEXT DEFAULT 'REUSABLE',
                created_date TEXT,
                source_project TEXT,
                location TEXT,
                notes TEXT
            )
            """)

            # Optimization Runs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                objective TEXT NOT NULL,
                execution_time_sec REAL NOT NULL,
                is_proven_optimal INTEGER NOT NULL,
                solver_status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """)
            
            conn.commit()

    def seed_standard_sections(self):
        """Seed default European and American structural sections into materials catalog."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM materials")
            if cursor.fetchone()["count"] == 0:
                entries = []
                for family, profiles in STANDARD_SECTIONS.items():
                    fam_name = family.split()[0]
                    for desig, wt in profiles:
                        # Insert with standard grade S355JR as initial catalog entries
                        entries.append((desig, fam_name, "S355JR", wt, "LINEAR", "Standard Profile"))
                        entries.append((desig, fam_name, "S275JR", wt, "LINEAR", "Standard Profile"))
                cursor.executemany("""
                INSERT OR IGNORE INTO materials (designation, family, grade, weight_kg_per_m, material_type, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """, entries)
                conn.commit()
