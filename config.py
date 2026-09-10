"""
Central configuration for the Steel Coil Warehouse Tracking prototype.

Everything that describes the physical warehouse layout (columns, slot
counts, dimensions, virtual receiver placement) lives here so the rest of
the code never hard-codes warehouse geometry.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The app's own directory is ephemeral on some hosts (e.g. Streamlit
# Community Cloud wipes it on redeploy/reboot) - that would silently reset
# every coil, tag, movement record, and the stored OneDrive connection.
# This warehouse's existing Slitter Streamlit app already solves the same
# problem for itself by preferring a persistent storage mount when one is
# available; the same candidate-path approach is reused here so the two
# apps behave consistently on the same host.
LEGACY_DATA_DIR = os.path.join(BASE_DIR, "data")
LEGACY_DB_PATH = os.path.join(LEGACY_DATA_DIR, "warehouse.db")


def _get_secret(key: str) -> str:
    try:
        import streamlit as st
        return str(st.secrets.get(key, "")).strip()
    except Exception:
        return ""


def _resolve_persistent_root() -> str:
    candidates = [
        _get_secret("WAREHOUSE_DATA_DIR"),
        os.getenv("WAREHOUSE_DATA_DIR", ""),
        "/mount/data/warehouse_persistent",
        "/data/warehouse_persistent",
        os.path.join(str(Path.home()), ".warehouse_persistent"),
    ]
    for candidate in candidates:
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".write_test")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            return candidate
        except Exception:
            continue
    os.makedirs(LEGACY_DATA_DIR, exist_ok=True)
    return LEGACY_DATA_DIR


DATA_DIR = _resolve_persistent_root()
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
# How often the Live Map's auto-refresh fragment re-fetches and redraws
# the chart. Streamlit/Plotly redraws the whole chart element on every
# tick (a brief flash is a property of that component, not something
# app code can fully suppress), so this is a straight trade-off between
# how current the map looks and how often it visibly flashes. 12s was
# chosen as a calmer default than the original 5s; lower it if you want
# faster updates and can live with more frequent flashing.
LIVE_MAP_REFRESH_SECONDS = 12

MOVEMENT_TYPE_SIMULATED = "SIMULATED"
MOVEMENT_TYPE_PRODUCTION = "PRODUCTION"

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------
# Fixed seed so the initial coil layout (positions, materials, weights) is
# identical every time the database is freshly created - e.g. after a
# container restart on a host with an ephemeral filesystem. Movements
# triggered afterward via Simulation Control are reseeded with OS entropy
# (see backend/database.py) so they stay unpredictable.
DEMO_SEED = 42

# ---------------------------------------------------------------------------
# Live map appearance
# ---------------------------------------------------------------------------
LIVE_MAP_HEIGHT = 760
