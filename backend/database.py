"""
Database access layer.

This module is the ONLY place that knows how to open a connection and how
the schema is created. Everything else in the app (models.py, simulation.py,
tag_manager.py, pages/*) goes through the functions here.

The prototype uses SQLite for zero-setup local development. To migrate to
PostgreSQL later, this module is the only file that needs a real rewrite
(swap sqlite3 for psycopg2 / SQLAlchemy and adjust the SQL dialect where
needed) - no other module touches SQL directly.
"""

import sqlite3
import random
from contextlib import contextmanager
from datetime import datetime, timedelta

import config


def get_connection():
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_cursor(commit=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    position_id TEXT PRIMARY KEY,
    area TEXT NOT NULL,
    column_name TEXT NOT NULL,
    slot REAL NOT NULL,
    level TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    tag_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    coil_id TEXT
);

CREATE TABLE IF NOT EXISTS coils (
    coil_id TEXT PRIMARY KEY,
    material TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    width_mm REAL NOT NULL,
    status TEXT NOT NULL,
    current_position TEXT,
    previous_position TEXT,
    tag_id TEXT,
    last_movement TEXT,
    last_seen TEXT,
    location_confidence REAL
);

CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    coil_id TEXT NOT NULL,
    tag_id TEXT,
    from_position TEXT,
    to_position TEXT,
    movement_type TEXT NOT NULL,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db():
    """Create tables if needed and seed demo data on first run."""
    with get_cursor(commit=True) as cur:
        cur.executescript(SCHEMA)

        cur.execute("SELECT COUNT(*) AS c FROM positions")
        if cur.fetchone()["c"] == 0:
            _seed_positions(cur)

        cur.execute("SELECT COUNT(*) AS c FROM tags")
        if cur.fetchone()["c"] == 0:
            _seed_tags(cur)

        cur.execute("SELECT COUNT(*) AS c FROM coils")
        if cur.fetchone()["c"] == 0:
            # Deterministic initial layout: every fresh database (e.g. after
            # a restart on a host with an ephemeral filesystem) starts with
            # the same coil positions/materials/weights, so the demo doesn't
            # visibly "reshuffle" on every reboot.
            random.seed(config.DEMO_SEED)
            _seed_coils(cur)
            _seed_movements(cur)
            # Reseed from OS entropy so movements simulated afterward via
            # Simulation Control stay unpredictable.
            random.seed()


def _seed_positions(cur):
    rows = []
    step = config.AREA_LENGTH_M / (config.SLOTS_PER_COLUMN - 1)
    for col in config.COLUMNS:
        y = config.COLUMN_Y[col]
        # Ground positions
        for slot in range(1, config.SLOTS_PER_COLUMN + 1):
            pos_id = f"{col}{slot}"
            x = (slot - 1) * step
            rows.append((pos_id, config.AREA_1, col, float(slot), config.GROUND, x, y))
        # Upper positions between neighbors
        for slot in range(1, config.SLOTS_PER_COLUMN):
            pos_id = f"{col}{slot}_{slot + 1}_UPPER"
            x = (slot - 0.5) * step
            rows.append(
                (pos_id, config.AREA_1, col, slot + 0.5, config.UPPER, x, y + config.UPPER_Y_OFFSET)
            )

    cur.executemany(
        "INSERT INTO positions (position_id, area, column_name, slot, level, x, y) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_tags(cur):
    rows = [(f"TAG-{i:03d}", config.TAG_STATUS_AVAILABLE, None) for i in range(1, config.NUM_TAGS + 1)]
    cur.executemany("INSERT INTO tags (tag_id, status, coil_id) VALUES (?, ?, ?)", rows)


def _seed_coils(cur):
    cur.execute("SELECT position_id FROM positions WHERE level = ?", (config.GROUND,))
    ground_positions = [r["position_id"] for r in cur.fetchall()]
    random.shuffle(ground_positions)

    now = datetime.now()

    for i in range(1, config.NUM_TRIAL_COILS + 1):
        coil_id = f"C{i:04d}"
        tag_id = f"TAG-{i:03d}"
        position = ground_positions[i - 1]
        material = random.choice(config.MATERIALS)
        weight = round(random.uniform(config.WEIGHT_MIN_KG, config.WEIGHT_MAX_KG), 0)
        width = round(random.uniform(config.WIDTH_MIN_MM, config.WIDTH_MAX_MM), 0)
        confidence = round(random.uniform(config.CONFIDENCE_MIN, config.CONFIDENCE_MAX), 1)
        last_seen = (now - timedelta(minutes=random.randint(0, 120))).isoformat(timespec="seconds")

        cur.execute(
            """
            INSERT INTO coils (coil_id, material, weight_kg, width_mm, status,
                                current_position, previous_position, tag_id,
                                last_movement, last_seen, location_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                coil_id, material, weight, width, config.COIL_STATUS_STATIONARY,
                position, None, tag_id, None, last_seen, confidence,
            ),
        )
        cur.execute(
            "UPDATE tags SET status = ?, coil_id = ? WHERE tag_id = ?",
            (config.TAG_STATUS_IN_USE, coil_id, tag_id),
        )


def _seed_movements(cur):
    """A handful of initial history records so the Movement History page
    is not empty on first launch."""
    cur.execute("SELECT coil_id, tag_id, current_position FROM coils LIMIT 5")
    coils = cur.fetchall()
    now = datetime.now()
    for i, coil in enumerate(coils):
        ts = (now - timedelta(minutes=(i + 1) * 15)).isoformat(timespec="seconds")
        confidence = round(random.uniform(config.CONFIDENCE_MIN, config.CONFIDENCE_MAX), 1)
        cur.execute(
            """
            INSERT INTO movements (timestamp, coil_id, tag_id, from_position, to_position,
                                    movement_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, coil["coil_id"], coil["tag_id"], None, coil["current_position"],
             config.MOVEMENT_TYPE_SIMULATED, confidence),
        )
