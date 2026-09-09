"""
Central configuration for the Steel Coil Warehouse Tracking prototype.

Everything that describes the physical warehouse layout (columns, slot
counts, dimensions, virtual receiver placement) lives here so the rest of
the code never hard-codes warehouse geometry.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "warehouse.db")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Warehouse geometry - Area 1
# ---------------------------------------------------------------------------
AREA_1 = "AREA_1"
AREA_LENGTH_M = 20.0
AREA_WIDTH_M = 10.0

COLUMNS = ["A", "B", "C", "D", "E"]
SLOTS_PER_COLUMN = 15

# y-coordinate (meters) assigned to each column, spread across the width of
# the warehouse with room left for aisles in between.
COLUMN_Y = {
    "A": 9.0,
    "B": 7.0,
    "C": 5.0,
    "D": 3.0,
    "E": 1.0,
}

# Vertical offset applied to an UPPER position so it renders visually above
# its two neighboring ground positions on the map.
UPPER_Y_OFFSET = 0.6

GROUND = "GROUND"
UPPER = "UPPER"

# ---------------------------------------------------------------------------
# Coil / Tag statuses
# ---------------------------------------------------------------------------
COIL_STATUS_STATIONARY = "STATIONARY"
COIL_STATUS_MOVING = "MOVING"
COIL_STATUS_PRODUCTION = "PRODUCTION"
COIL_STATUS_MISSING = "MISSING"

COIL_STATUSES = [
    COIL_STATUS_STATIONARY,
    COIL_STATUS_MOVING,
    COIL_STATUS_PRODUCTION,
    COIL_STATUS_MISSING,
]

TAG_STATUS_IN_USE = "IN_USE"
TAG_STATUS_AVAILABLE = "AVAILABLE"

NUM_TAGS = 20
NUM_TRIAL_COILS = 20

MATERIALS = ["DX51D", "S235", "S355", "DC01", "Galvanized Steel"]

WEIGHT_MIN_KG = 4000
WEIGHT_MAX_KG = 12000
WIDTH_MIN_MM = 900
WIDTH_MAX_MM = 1600

# ---------------------------------------------------------------------------
# Simulated BLE receivers (virtual gateways) for Area 1
# ---------------------------------------------------------------------------
NUM_RECEIVERS = 10
RECEIVERS = {
    f"RX{i+1}": {
        "x": (i % 5) * (AREA_LENGTH_M / 4),
        "y": AREA_WIDTH_M if i < 5 else 0.0,
    }
    for i in range(NUM_RECEIVERS)
}

# ---------------------------------------------------------------------------
# Location confidence simulation
# ---------------------------------------------------------------------------
CONFIDENCE_MIN = 65
CONFIDENCE_MAX = 98
LOW_CONFIDENCE_THRESHOLD = 75

# ---------------------------------------------------------------------------
# Simulation timing
# ---------------------------------------------------------------------------
MOVEMENT_TRAVEL_SECONDS = 2.0
LIVE_MAP_REFRESH_SECONDS = 5

MOVEMENT_TYPE_SIMULATED = "SIMULATED"
MOVEMENT_TYPE_PRODUCTION = "PRODUCTION"
