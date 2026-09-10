"""
Import the real coil stock list from an exported Excel workbook.

This replaces the simulated demo coils with the warehouse's actual stock,
read from a fixed sheet/column layout:

    Sheet "ΑΠΟΘΗΚΗ" - row 1 is headers, the last row is a sums row (ignored).

    Column F  - unique coil id
    Column I  - map column, 1..5 -> A..E (anything else is skipped for now)
    Column H  - position within the column:
                  a single number (e.g. 5)   -> ground position, e.g. D5
                  a pair (e.g. "4,5"/"4-5",
                  or a value like 4.5)        -> upper position between the
                                                 two neighbors, e.g. B4_5_UPPER
    Column Q  - "Y" marks the coil as locked (shown with a red lock icon)
    Columns A, B, C, D, E, G, K, P, R
              - free-form details shown in the coil popup, labeled with
                whatever header text row 1 has for that column (e.g. the
                "K" column's header "ΚΑΤΗΓΟΡΙΑ" becomes the label for its
                value).

Column letters are used instead of header names to locate values, since
header text is in Greek and may not always be present/well-formed, but
the layout is a fixed set of columns.
"""

import json
import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from openpyxl.utils import column_index_from_string

import config
from backend.database import get_cursor

SHEET_NAME = "ΑΠΟΘΗΚΗ"

COIL_ID_COL = "F"
MAP_COLUMN_COL = "I"
POSITION_COL = "H"
LOCK_COL = "Q"
EXTRA_COLS = ["A", "B", "C", "D", "E", "G", "K", "P", "R"]


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)


def _col(letter: str) -> int:
    return column_index_from_string(letter) - 1


def _cell(row, idx):
    if idx >= len(row):
        return None
    val = row.iloc[idx]
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return val


def _parse_position_slot(raw) -> Optional[tuple]:
    """Returns ("GROUND", slot, None) or ("UPPER", low, high), or None if
    the value can't be parsed."""
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        f = float(raw)
        if f.is_integer():
            return ("GROUND", int(f), None)
        low = int(f)
        return ("UPPER", low, low + 1)

    s = str(raw).strip()
    if not s:
        return None

    for sep in (",", "-", "/"):
        if sep in s:
            parts = [p.strip() for p in s.split(sep) if p.strip()]
            if len(parts) == 2:
                try:
                    a, b = int(float(parts[0])), int(float(parts[1]))
                except ValueError:
                    return None
                return ("UPPER", min(a, b), max(a, b))

    try:
        f = float(s)
    except ValueError:
        return None
    if f.is_integer():
        return ("GROUND", int(f), None)
    low = int(f)
    return ("UPPER", low, low + 1)


def _build_position_id(column_num, raw_position) -> Optional[str]:
    try:
        col_idx = int(float(column_num))
    except (TypeError, ValueError):
        return None
    if col_idx < 1 or col_idx > len(config.COLUMNS):
        return None
    col_letter = config.COLUMNS[col_idx - 1]

    parsed = _parse_position_slot(raw_position)
    if parsed is None:
        return None

    kind, low, high = parsed
    if kind == "GROUND":
        return f"{col_letter}{low}"
    return f"{col_letter}{low}_{high}_UPPER"


def _existing_position_ids() -> set:
    with get_cursor() as cur:
        cur.execute("SELECT position_id FROM positions")
        return {r["position_id"] for r in cur.fetchall()}


def clear_all_coils(cur):
    """Remove every coil and release every tag, ahead of a full stock
    import. Movement history is left intact."""
    cur.execute("SELECT tag_id FROM tags WHERE coil_id IS NOT NULL")
    in_use_tags = [r["tag_id"] for r in cur.fetchall()]
    for tag_id in in_use_tags:
        cur.execute(
            "UPDATE tags SET status = ?, coil_id = NULL WHERE tag_id = ?",
            (config.TAG_STATUS_AVAILABLE, tag_id),
        )
    cur.execute("DELETE FROM coils")


def import_stock_from_excel(file, replace_existing: bool = True) -> ImportResult:
    result = ImportResult()

    try:
        df = pd.read_excel(file, sheet_name=SHEET_NAME, header=0, engine="openpyxl")
    except Exception as e:
        result.errors.append(f"Could not read sheet '{SHEET_NAME}': {e}")
        return result

    if df.empty:
        result.errors.append("Sheet is empty.")
        return result

    # Last row is a sums row - ignore it.
    df = df.iloc[:-1]

    valid_positions = _existing_position_ids()

    idx = {letter: _col(letter) for letter in
           {COIL_ID_COL, MAP_COLUMN_COL, POSITION_COL, LOCK_COL, *EXTRA_COLS}}
    header_labels = {letter: (df.columns[idx[letter]] if idx[letter] < len(df.columns) else letter)
                      for letter in EXTRA_COLS}

    rows_to_insert = []
    now = None
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")

    for row_num, row in df.iterrows():
        coil_id = _cell(row, idx[COIL_ID_COL])
        if coil_id is None:
            continue
        coil_id = str(coil_id).strip()
        if not coil_id:
            continue

        column_num = _cell(row, idx[MAP_COLUMN_COL])
        position_raw = _cell(row, idx[POSITION_COL])
        position_id = _build_position_id(column_num, position_raw)

        if position_id is None:
            result.skipped += 1
            result.errors.append(
                f"Row {row_num + 2}: coil {coil_id} - could not parse column/position "
                f"(I={column_num!r}, H={position_raw!r})."
            )
            continue

        if position_id not in valid_positions:
            result.skipped += 1
            result.errors.append(
                f"Row {row_num + 2}: coil {coil_id} - position {position_id} does not "
                f"exist in Area 1's layout."
            )
            continue

        lock_val = _cell(row, idx[LOCK_COL])
        locked = 1 if (lock_val is not None and str(lock_val).strip().upper() == "Y") else 0

        extra = {}
        for letter in EXTRA_COLS:
            val = _cell(row, idx[letter])
            if val is not None:
                extra[str(header_labels[letter])] = val

        rows_to_insert.append((coil_id, position_id, locked, json.dumps(extra, default=str), now))

    if not rows_to_insert:
        result.errors.append("No valid coil rows found to import.")
        return result

    with get_cursor(commit=True) as cur:
        if replace_existing:
            clear_all_coils(cur)

        for coil_id, position_id, locked, extra_json, ts in rows_to_insert:
            cur.execute(
                """
                INSERT INTO coils (coil_id, material, weight_kg, width_mm, status,
                                    current_position, previous_position, tag_id,
                                    last_movement, last_seen, location_confidence,
                                    extra_fields, locked)
                VALUES (?, '', 0, 0, ?, ?, NULL, NULL, NULL, ?, NULL, ?, ?)
                ON CONFLICT(coil_id) DO UPDATE SET
                    current_position = excluded.current_position,
                    extra_fields = excluded.extra_fields,
                    locked = excluded.locked,
                    last_seen = excluded.last_seen
                """,
                (coil_id, config.COIL_STATUS_STATIONARY, position_id, ts, extra_json, locked),
            )
            result.imported += 1

    return result
