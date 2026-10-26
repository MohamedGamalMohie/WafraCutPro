# WafraCutPro — Professional Steel Nesting & Cutting Optimization Software for Windows

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20(64--bit)-blue)
![GUI](https://img.shields.io/badge/GUI-PyQt6-brightgreen)
![Solver](https://img.shields.io/badge/Optimization-OR--Tools%20CP--SAT-orange)
![Reports](https://img.shields.io/badge/Reports-Excel%208--Sheet%20openpyxl-green)

**SteelNest Pro** is an engineering-grade Windows desktop application engineered for structural steel fabricators, manufacturing workshops, and technical estimation offices. It optimizes cutting plans for structural steel sections (beams, columns, hollow sections, angles, pipes) and steel plates, minimizing material waste while strictly respecting physical fabrication constraints.

---

## 🏗️ Supported Material Categories

### 1. Structural Steel Sections (1D Linear Profiles)
- **I & H Beams**: IPE (80 to 600), IPN, HEA (100 to 600), HEB (100 to 600), HEM, and AISC W-Shapes.
- **Channels**: UPN (50 to 400), UPE, and structural channels.
- **Angles**: Equal & unequal angles (L 40×4 to L 200×20).
- **Hollow Sections**: SHS (Square) and RHS (Rectangular) from 40×40 up to 300×200.
- **Pipes**: CHS Circular Hollow Sections & industrial steel pipes.
- **Solid Bars**: Flat bars, round bars, square bars, and custom user-defined sections.

### 2. Steel Plates and Sheets (2D Rectangular Nesting)
- Standard stock plate sizes (e.g., 2000×6000 mm, 2500×12000 mm, or custom).
- Thicknesses from 1 mm to 150+ mm with material grade pairing.
- 90° part rotation toggle, plasma/flame/laser kerf, and perimeter safety margins.
- Rectangular packing engine with collision avoidance and guillotine shearing constraints.

---

## ⚡ Three Essential Linear Nesting Modes

SteelNest Pro features three distinct mathematical nesting modes implemented as strict business rules:

| Nesting Mode | Objective & Rule Enforcement | Typical Use Case |
| :--- | :--- | :--- |
| **Mode 1: Free Nesting** *(Minimum Material Waste)* | • Combines multiple cut pieces of the same section on each stock bar.<br>• Solves cutting stock patterns via **OR-Tools CP-SAT**.<br>• Minimizes raw stock consumption and scrap percentage. | General fabrication, trusses, roof frames, high-volume production. |
| **Mode 2: Single Cut per Bar** *(Strict 1 Cut / Bar)* | • Strictly limits each stock bar to **at most ONE finished piece**.<br>• Never combines two parts on the same bar.<br>• Accurately reports remaining bar length as offcut/waste. | Heavy crane girders, specialized splice-free elements, strict quality contracts. |
| **Mode 3: Double Cuts per Bar** *(Max 2 Cuts / Bar)* | • Strictly restricts each bar to **one or two finished pieces**.<br>• Never places 3 or more pieces on a single bar.<br>• Solves optimal pairwise cut matching. | Dual-head automatic sawing lines, transport-limited handling. |

> **Comparative Evaluation**: SteelNest Pro provides a **"Compare All 3 Modes Side-by-Side"** feature allowing production managers to evaluate material consumption differences instantly.

---

## 📊 Professional 8-Sheet Production Excel Export

The reporting engine (`openpyxl`) generates an 8-sheet engineering workbook:

1. **Executive Summary**: Project metadata, solver status, total stock consumed, utilization %, waste %, and purchasing costs.
2. **Detailed Cutting Plan**: Bar-by-bar cutting breakdown, part cut marks, saw kerf, end trimming allowances, used length, and offcut classification.
3. **Cut List**: Part marks, required vs nested quantities, and assignment status (`COMPLETED`, `PARTIAL`, `UNASSIGNED`).
4. **Stock Purchase List**: Inventory stock vs required bars, calculating shortages and purchase quantities.
5. **Remnants and Offcuts**: Traceability for usable offcuts with IDs, lengths, and warehouse rack references.
6. **Material Summary**: Aggregated lengths, piece counts, and utilization grouped by section designation and grade.
7. **Plate Nesting**: 2D layout metrics, stock plate sizes, positioned part marks, and area metrics.
8. **Unprocessed Exceptions**: Audit log of any unassigned or infeasible parts with engineering failure reasons.

---

## 📐 Graphical Visualization

- **1D Linear Stock Bars**: Correctly scaled segments, distinctive part mark colors, start/end trimming indicators, kerf cuts, and color-coded remnant/scrap badges.
- **2D Steel Plates**: Scaled plates showing safety margins, placed parts with part marks, $(w \times l)$ dimensions, rotation indicators, and unused area.

---

## 💻 Technical Architecture

```
steel_nest_pro/
├── main.py                     # Root Windows launcher
├── build_windows.py            # PyInstaller standalone packaging script
├── requirements.txt            # Python dependencies
├── sample_data/                # Input templates and sample production reports
├── steel_nest/
│   ├── app.py                  # PyQt6 entry point with High DPI & Dark Theme
│   ├── config.py               # Constants, profiles catalog, grades, defaults
│   ├── database/
│   │   ├── db_manager.py       # SQLite connection manager & schema init
│   │   └── repositories.py     # CRUD repositories for Projects, Stock, Cuts, Remnants
│   ├── models/
│   │   ├── material.py         # SteelProfile, PlateSpecification
│   │   ├── stock.py            # StockItem, RemnantItem
│   │   ├── part.py             # PartCutItem (1D), PlatePartItem (2D)
│   │   ├── nesting_plan.py     # CutSegment, LinearBarPlan, PlateNestPlan, OptimizationResult
│   │   └── project.py          # Project, ProjectSettings
│   ├── core/
│   │   ├── validation.py       # Dimensional and material compatibility validation
│   │   ├── linear_optimizer.py # Modes 1, 2, 3 with OR-Tools CP-SAT & BFD
│   │   ├── plate_optimizer.py  # 2D rectangular nesting engine
│   │   └── remnant_manager.py  # Usable offcuts extraction & inventory persistence
│   ├── reporting/
│   │   ├── excel_exporter.py   # 8-sheet Excel reporting module
│   │   ├── excel_importer.py   # Excel/CSV parser with header detection
│   │   └── template_generator.py# Downloadable blank input templates
│   └── ui/
│       ├── main_window.py      # Main window & sidebar navigation
│       ├── themes.py           # Modern dark steel engineering stylesheet
│       ├── widgets/
│       │   ├── bar_visualizer.py   # QPainter 1D scaled bar widget
│       │   ├── plate_visualizer.py # QPainter 2D scaled plate layout widget
│       │   └── kpi_card.py         # Metric cards
│       ├── views/
│       │   ├── dashboard_view.py   # KPIs, recent projects, shortages
│       │   ├── projects_view.py    # Project manager & duplication
│       │   ├── cut_list_view.py    # 1D/2D requirements, import/export
│       │   ├── inventory_view.py   # Raw stock & demo seeding
│       │   ├── linear_nesting_view.py # Mode 1/2/3 selection & solver
│       │   ├── plate_nesting_view.py  # 2D plate nesting view
│       │   ├── results_view.py     # Graphical cutting layouts
│       │   ├── reports_view.py     # Excel generator
│       │   ├── remnants_view.py    # Offcuts inventory
│       │   └── database_view.py    # Profiles database
│       └── workers/
│           └── optimization_worker.py # QThread for non-blocking solving
└── tests/
    └── test_comprehensive_cases.py # 14 mandatory test cases
```

---

## 🚀 Installation & Running

### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.12+

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Launch the Application
```powershell
python main.py
```

---

## 🧪 Automated Testing

All 14 mandatory test cases are verified via pytest:

```powershell
python -m pytest tests/test_comprehensive_cases.py -v
```

### Verification Matrix
- `test_case_01`: Exact fit on 12 m bar (5 m + 7 m) with zero kerf/trim.
- `test_case_02`: Kerf and trimming allowances verification on 12 m bar (5 m + 6 m).
- `test_case_03`: Single Cut Mode strictly restricts bars to 1 part max.
- `test_case_04`: Double Cuts Mode strictly restricts bars to 2 parts max.
- `test_case_05`: Free Nesting combines 4+ pieces on a bar.
- `test_case_06`: Usable stock length is never exceeded in any pattern.
- `test_case_07`: Inventory limits tracked and shortages detected.
- `test_case_08`: Infeasible parts reported with clear failure reasons.
- `test_case_09`: Incompatible sections and grades are never mixed.
- `test_case_10`: Remnants calculated accurately without double counting kerf/trim.
- `test_case_11`: 2D plate nesting produces non-overlapping parts within margins.
- `test_case_12`: Excel exports match optimizer results across all 8 sheets.
- `test_case_13`: Saved projects reproduce input data and settings on reload.
- `test_case_14`: Large input batches (150+ cuts) handled smoothly without crashing.

---

## 📦 Building Standalone Windows Executable

To generate a standalone Windows application using PyInstaller:

```powershell
python build_windows.py
```

The resulting folder and `.exe` will be located in:
`dist/SteelNestPro/SteelNestPro.exe`
