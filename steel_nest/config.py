"""
WafraCut Pro - Global Configuration and Constants
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple

APP_NAME = "WafraCut Pro"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "WafraCut Technologies"

# Optimization Modes
class LinearOptimizationMode(str, Enum):
    FREE_NESTING = "FREE_NESTING"          # Mode 1: Minimum Waste (Multi-cut per bar)
    SINGLE_CUT = "SINGLE_CUT"              # Mode 2: Exactly ONE cut per bar
    DOUBLE_CUT = "DOUBLE_CUT"              # Mode 3: Max TWO cuts per bar

class NestingObjective(str, Enum):
    MIN_WASTE = "MIN_WASTE"
    MIN_BARS = "MIN_BARS"
    MIN_COST = "MIN_COST"
    BALANCED = "BALANCED"

class MaterialType(str, Enum):
    LINEAR = "LINEAR"
    PLATE = "PLATE"

class RemnantStatus(str, Enum):
    REUSABLE = "REUSABLE"
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    DISCARDED = "DISCARDED"

# Standard Steel Grades
STANDARD_STEEL_GRADES = [
    "S235JR",
    "S275JR",
    "S355JR",
    "S355J2",
    "S355J2+N",
    "S460M",
    "ASTM A36",
    "ASTM A572 Gr.50",
    "ASTM A992",
    "SS400"
]

# Standard Stock Lengths (mm)
DEFAULT_STOCK_LENGTHS = [6000.0, 9000.0, 12000.0, 14000.0, 15000.0]

# Standard Plate Dimensions (mm)
DEFAULT_PLATE_DIMENSIONS = [
    (1500.0, 6000.0),
    (2000.0, 6000.0),
    (2000.0, 12000.0),
    (2500.0, 8000.0),
    (2500.0, 12000.0),
    (3000.0, 12000.0)
]

# Standard Sections catalog with weight kg/m
STANDARD_SECTIONS: Dict[str, List[Tuple[str, float]]] = {
    "IPE": [
        ("IPE 80", 6.0), ("IPE 100", 8.1), ("IPE 120", 10.4), ("IPE 140", 12.9),
        ("IPE 160", 15.8), ("IPE 180", 18.8), ("IPE 200", 22.4), ("IPE 220", 26.2),
        ("IPE 240", 30.7), ("IPE 270", 36.1), ("IPE 300", 42.2), ("IPE 330", 49.1),
        ("IPE 360", 57.1), ("IPE 400", 66.3), ("IPE 450", 77.6), ("IPE 500", 90.7),
        ("IPE 550", 106.0), ("IPE 600", 122.0)
    ],
    "HEA": [
        ("HEA 100", 16.7), ("HEA 120", 19.9), ("HEA 140", 24.7), ("HEA 160", 30.4),
        ("HEA 180", 35.5), ("HEA 200", 42.3), ("HEA 220", 50.5), ("HEA 240", 60.3),
        ("HEA 260", 68.2), ("HEA 280", 76.4), ("HEA 300", 88.3), ("HEA 320", 97.6),
        ("HEA 340", 105.0), ("HEA 360", 112.0), ("HEA 400", 125.0), ("HEA 450", 140.0),
        ("HEA 500", 155.0), ("HEA 600", 178.0)
    ],
    "HEB": [
        ("HEB 100", 20.4), ("HEB 120", 26.7), ("HEB 140", 33.7), ("HEB 160", 42.6),
        ("HEB 180", 51.2), ("HEB 200", 61.3), ("HEB 220", 71.5), ("HEB 240", 83.2),
        ("HEB 260", 93.0), ("HEB 280", 103.0), ("HEB 300", 117.0), ("HEB 320", 127.0),
        ("HEB 340", 134.0), ("HEB 360", 142.0), ("HEB 400", 155.0), ("HEB 500", 187.0),
        ("HEB 600", 212.0)
    ],
    "UPN": [
        ("UPN 50", 5.59), ("UPN 65", 7.09), ("UPN 80", 8.64), ("UPN 100", 10.6),
        ("UPN 120", 13.4), ("UPN 140", 16.0), ("UPN 160", 18.8), ("UPN 180", 22.0),
        ("UPN 200", 25.3), ("UPN 220", 29.4), ("UPN 240", 33.2), ("UPN 260", 37.9),
        ("UPN 280", 41.8), ("UPN 300", 46.2), ("UPN 350", 60.6), ("UPN 400", 71.8)
    ],
    "L (Angle)": [
        ("L 40x40x4", 2.42), ("L 50x50x5", 3.77), ("L 60x60x6", 5.42), ("L 70x70x7", 7.38),
        ("L 80x80x8", 9.63), ("L 90x90x9", 12.2), ("L 100x100x10", 15.0),
        ("L 120x120x12", 21.6), ("L 150x150x15", 33.8), ("L 200x200x20", 59.9)
    ],
    "SHS (Square Hollow)": [
        ("SHS 40x40x3", 3.45), ("SHS 50x50x4", 5.72), ("SHS 60x60x4", 7.04),
        ("SHS 80x80x5", 11.7), ("SHS 100x100x6", 17.5), ("SHS 120x120x6", 21.3),
        ("SHS 150x150x8", 35.1), ("SHS 200x200x10", 58.7), ("SHS 250x250x12", 87.6)
    ],
    "RHS (Rectangular Hollow)": [
        ("RHS 60x40x3", 4.39), ("RHS 80x40x4", 6.97), ("RHS 100x50x4", 8.86),
        ("RHS 120x60x5", 13.3), ("RHS 150x100x6", 22.2), ("RHS 200x100x8", 35.1),
        ("RHS 250x150x10", 58.7), ("RHS 300x200x10", 74.4)
    ],
    "CHS (Circular Pipe)": [
        ("CHS 48.3x3.2", 3.56), ("CHS 60.3x3.6", 5.03), ("CHS 76.1x4.0", 7.11),
        ("CHS 88.9x4.5", 9.37), ("CHS 114.3x5.0", 13.5), ("CHS 139.7x6.3", 20.7),
        ("CHS 168.3x7.1", 28.2), ("CHS 219.1x8.0", 41.6), ("CHS 273.0x10.0", 64.9)
    ]
}

# Standard Default Cutting Parameters
DEFAULT_KERF = 3.0           # mm (Saw blade width)
DEFAULT_TRIM_START = 15.0    # mm (End trimming for square / clean cut)
DEFAULT_TRIM_END = 15.0      # mm (End trimming)
DEFAULT_MIN_REMNANT = 500.0  # mm (Minimum offcut length to be classified as reusable)
DEFAULT_TIME_LIMIT_SEC = 30  # seconds

# Plate Nesting Defaults
DEFAULT_PLATE_KERF = 4.0     # mm
DEFAULT_PLATE_MARGIN = 10.0  # mm from edge of plate
