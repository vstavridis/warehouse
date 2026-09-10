"""
Data-access helpers ("models") for coils, tags, positions and movements.

These functions return plain dicts / lists of dicts (or pandas DataFrames
where convenient for Streamlit) so the UI pages never need to know the
underlying SQL or storage engine.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import pandas as pd

from backend.database import get_cursor


def _now() -> str:
    """Consistent ISO-8601 timestamp used for every write in this app.

    Mixing this with SQLite's own `datetime('now')` (which uses a
    different, space-separated format) breaks strict pandas datetime
    parsing on newer pandas/Python versions, so every write goes through
    this single function instead.
    """
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Dataclasses (used mainly for type clarity / future hardware ingestion code)
# ---------------------------------------------------------------------------
@dataclass
class Position:
    position_id: str
    area: str
    column_name: str
    slot: float
    level: str
    x: float
    y: float


@dataclass
class Coil:
    coil_id: str
    material: str
    weight_kg: float
    width_mm: float
    status: str
    current_position: Optional[str]
    previous_position: Optional[str]
    tag_id: Optional[str]
    last_movement: Optional[str]
    last_seen: Optional[str]
    location_confidence: Optional[float]


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------
def get_all_positions() -> pd.DataFrame:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions")
        rows = [dict(r) for r in cur.fetchall()]
    return pd.DataFrame(rows)


def get_position(position_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE position_id = ?", (position_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_empty_positions() -> List[str]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT position_id FROM positions
            WHERE position_id NOT IN (
                SELECT current_position FROM coils WHERE current_position IS NOT NULL
            )
            ORDER BY position_id
            """
        )
        return [r["position_id"] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Coils
# ---------------------------------------------------------------------------
def get_all_coils() -> pd.DataFrame:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM coils ORDER BY coil_id")
        rows = [dict(r) for r in cur.fetchall()]
    return pd.DataFrame(rows)


def get_active_coils() -> pd.DataFrame:
    """Coils currently placed in the warehouse (not sent to production)."""
    df = get_all_coils()
    if df.empty:
        return df
    return df[df["current_position"].notna()]


def get_coil(coil_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM coils WHERE coil_id = ?", (coil_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_next_coil_id() -> str:
    with get_cursor() as cur:
        cur.execute("SELECT coil_id FROM coils ORDER BY coil_id DESC LIMIT 1")
        row = cur.fetchone()
    if not row:
        return "C0001"
    last_num = int(row["coil_id"][1:])
    return f"C{last_num + 1:04d}"


def create_coil(coil_id: str, material: str, weight_kg: float, width_mm: float,
                 position_id: str, tag_id: Optional[str] = None) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO coils (coil_id, material, weight_kg, width_mm, status,
                                current_position, previous_position, tag_id,
                                last_movement, last_seen, location_confidence)
            VALUES (?, ?, ?, ?, 'STATIONARY', ?, NULL, ?, NULL, ?, 90)
            """,
            (coil_id, material, weight_kg, width_mm, position_id, tag_id, _now()),
        )


def update_coil(coil_id: str, **fields) -> None:
    if not fields:
        return
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [coil_id]
    with get_cursor(commit=True) as cur:
        cur.execute(f"UPDATE coils SET {columns} WHERE coil_id = ?", values)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------
def get_all_tags() -> pd.DataFrame:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tags ORDER BY tag_id")
        rows = [dict(r) for r in cur.fetchall()]
    return pd.DataFrame(rows)


def get_tag(tag_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tags WHERE tag_id = ?", (tag_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_available_tags() -> List[str]:
    with get_cursor() as cur:
        cur.execute("SELECT tag_id FROM tags WHERE status = 'AVAILABLE' ORDER BY tag_id")
        return [r["tag_id"] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------
def add_movement(coil_id: str, tag_id: Optional[str], from_position: Optional[str],
                  to_position: Optional[str], movement_type: str, confidence: Optional[float]) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO movements (timestamp, coil_id, tag_id, from_position, to_position,
                                    movement_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_now(), coil_id, tag_id, from_position, to_position, movement_type, confidence),
        )


def get_movement_history() -> pd.DataFrame:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM movements ORDER BY timestamp DESC")
        rows = [dict(r) for r in cur.fetchall()]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Settings (generic key/value store, e.g. OneDrive sync state)
# ---------------------------------------------------------------------------
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: Optional[str]) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def delete_setting(key: str) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM settings WHERE key = ?", (key,))
