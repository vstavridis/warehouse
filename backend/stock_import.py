"""
Import the real coil stock list from an exported Excel workbook.

Column matching mirrors the technique already used by this warehouse's
existing "Slitter" Streamlit app to read the very same ΑΠΟΘΗΚΗ sheet:
resolve each field by its **header text** (accent/case/space-insensitive,
with a few alternate spellings tried per field) rather than a fixed
column letter, since that's far more robust to the sheet being edited
over time. The confirmed header names below are taken directly from that
app's own column-matching code.

    Sheet "ΑΠΟΘΗΚΗ" - row 1 is headers, the last row is a sums row (ignored).

    Coil id    - header "Νο ΡΟΛΛΟΥ" (falls back to column F if not found)
    Position   - header "ΘΕΣΗ" (falls back to column H): a single number
                 is a ground position (e.g. 5 -> D5); a pair ("4,5",
                 "4-5") or a value like 4.5 is an upper position
                 (e.g. -> B4_5_UPPER)
    Map column - no equivalent field in the Slitter app (it doesn't need
                 warehouse coordinates), so this still reads column I:
                 1..5 -> A..E (anything else is skipped)
    Locked     - no equivalent field either; still reads column Q, "Y"
                 marks the coil as locked (shown with a red lock icon)

    Descriptive fields shown in the coil popup, labeled with whatever
    header text the sheet actually has for that column (each tried by
    name, with fallbacks; a field missing from the sheet is just omitted):
        ΕΙΔΟΣ, ΠΟΙΟΤΗΤΑ, ΠΑΧΟΣ, ΔΙΑΣΤΑΣΕΙΣ/ΠΛΑΤΟΣ, ΒΑΡΟΣ, ΜΕΤΡΑ,
        ΠΡΟΕΛΕΥΣΗ, ΤΟΜΕΑΣ, ΚΑΤΗΓΟΡΙΑ, ΤΙΜΗ/PRICE, ΠΕΡΙΓΡΑΦΗ/Description
"""

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
from openpyxl.utils import column_index_from_string

import config
from backend.database import get_cursor
from backend.formatting import format_thickness, format_whole_number

SHEET_NAME = "ΑΠΟΘΗΚΗ"

COIL_ID_CANDIDATES = ["Νο ΡΟΛΛΟΥ", "No ΡΟΛΛΟΥ", "NO ΡΟΛΛΟΥ", "ΡΟΛΛΟ", "ΚΩΔΙΚΟΣ"]
POSITION_CANDIDATES = ["ΘΕΣΗ"]
MAP_COLUMN_CANDIDATES = ["ΣΤΗΛΗ", "ΣΕΙΡΑ ΑΠΟΘΗΚΗΣ"]
LOCK_CANDIDATES = ["ΚΛΕΙΔΩΜΕΝΟ", "LOCK", "LOCKED"]

# Fixed-letter fallbacks, used only when none of the header-name candidates
# above are found - keeps the importer working even against a sheet whose
# headers don't match any known spelling.
COIL_ID_FALLBACK_COL = "F"
POSITION_FALLBACK_COL = "H"
MAP_COLUMN_FALLBACK_COL = "I"
LOCK_FALLBACK_COL = "Q"

# Columns used to build each coil's search-dropdown label, given directly
# by column letter (not header name): coil id / material x thickness x
# width - weight / grade / origin / column-J value / category, e.g.
# "SID846713 / Galvanized 0,50 x 1000 - 9510 / DX51+Z140 / ΣΙΔΜΑ / 980 / A"
DROPDOWN_MATERIAL_COL = "A"
DROPDOWN_THICKNESS_COL = "B"
DROPDOWN_WIDTH_COL = "C"
DROPDOWN_WEIGHT_COL = "D"
DROPDOWN_GRADE_COL = "E"
DROPDOWN_ORIGIN_COL = "G"
DROPDOWN_J_COL = "J"
DROPDOWN_CATEGORY_COL = "K"

# Descriptive fields shown in the coil popup. Each entry is a list of
# header-name candidates for the same field; the first one found in the
# sheet is used, and displayed under its own (real) header text.
EXTRA_FIELD_CANDIDATES = [
    ["ΕΙΔΟΣ"],
    ["ΠΟΙΟΤΗΤΑ"],
    ["ΠΑΧΟΣ"],
    ["ΔΙΑΣΤΑΣΕΙΣ", "ΠΛΑΤΟΣ"],
    ["ΒΑΡΟΣ"],
    ["ΜΕΤΡΑ"],
    ["ΠΡΟΕΛΕΥΣΗ"],
    ["ΤΟΜΕΑΣ"],
    ["ΚΑΤΗΓΟΡΙΑ"],
    ["ΤΙΜΗ", "PRICE"],
    ["Description", "ΠΕΡΙΓΡΑΦΗ"],
]


def normalize_text(value) -> str:
    value = str(value).strip().lower()
    replacements = {
        "ά": "α", "έ": "ε", "ή": "η", "ί": "ι", "ό": "ο", "ύ": "υ", "ώ": "ω",
        "ϊ": "ι", "ΐ": "ι", "ϋ": "υ", "ΰ": "υ",
    }
    for a, b in replacements.items():
        value = value.replace(a, b)
    return re.sub(r"\s+", " ", value)


def normalize_key(value) -> str:
    return normalize_text(value).replace(" ", "")


def _resolve_column(columns, candidates) -> Optional[str]:
    """Returns the actual column label matching one of `candidates` by
    normalized text, or None if none match."""
    normalized = {normalize_key(c): c for c in columns}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _letter_column(df, letter) -> Optional[str]:
    idx = column_index_from_string(letter) - 1
    if idx < len(df.columns):
        return df.columns[idx]
    return None


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "<na>", "na"}:
        return None
    return value


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


def _build_dropdown_label(coil_id: str, row, letter_cols: dict) -> str:
    """SID846713 / Galvanized 0,50 x 1000 - 9510 / DX51+Z140 / ΣΙΔΜΑ / 980 / A"""

    def val(letter):
        col = letter_cols.get(letter)
        return _clean(row.get(col)) if col is not None else None

    material = val(DROPDOWN_MATERIAL_COL)
    thickness = val(DROPDOWN_THICKNESS_COL)
    width = val(DROPDOWN_WIDTH_COL)
    weight = val(DROPDOWN_WEIGHT_COL)
    grade = val(DROPDOWN_GRADE_COL)
    origin = val(DROPDOWN_ORIGIN_COL)
    j_value = val(DROPDOWN_J_COL)
    category = val(DROPDOWN_CATEGORY_COL)

    spec_bits = []
    if material is not None:
        spec_bits.append(str(material))
    if thickness is not None or width is not None or weight is not None:
        spec_bits.append(
            f"{format_thickness(thickness) if thickness is not None else '?'} x "
            f"{format_whole_number(width) if width is not None else '?'} - "
            f"{format_whole_number(weight) if weight is not None else '?'}"
        )
    spec = " ".join(spec_bits)

    segments = [
        coil_id, spec, grade, origin,
        format_whole_number(j_value) if j_value is not None else None,
        category,
    ]
    return " / ".join(str(s) for s in segments if s not in (None, ""))


def _existing_position_ids() -> set:
    with get_cursor() as cur:
        cur.execute("SELECT position_id FROM positions")
        return {r["position_id"] for r in cur.fetchall()}


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)
    matched_columns: dict = field(default_factory=dict)


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

    coil_id_col = (_resolve_column(df.columns, COIL_ID_CANDIDATES)
                   or _letter_column(df, COIL_ID_FALLBACK_COL))
    position_col = (_resolve_column(df.columns, POSITION_CANDIDATES)
                     or _letter_column(df, POSITION_FALLBACK_COL))
    map_column_col = (_resolve_column(df.columns, MAP_COLUMN_CANDIDATES)
                       or _letter_column(df, MAP_COLUMN_FALLBACK_COL))
    lock_col = (_resolve_column(df.columns, LOCK_CANDIDATES)
                or _letter_column(df, LOCK_FALLBACK_COL))

    result.matched_columns = {
        "Coil id": coil_id_col, "Position": position_col,
        "Map column": map_column_col, "Locked": lock_col,
    }

    if coil_id_col is None:
        result.errors.append("Could not find a coil id column.")
        return result

    extra_cols = []
    for candidates in EXTRA_FIELD_CANDIDATES:
        col = _resolve_column(df.columns, candidates)
        if col is not None:
            extra_cols.append(col)
            result.matched_columns[candidates[0]] = col

    dropdown_letter_cols = {
        letter: _letter_column(df, letter)
        for letter in (
            DROPDOWN_MATERIAL_COL, DROPDOWN_THICKNESS_COL, DROPDOWN_WIDTH_COL,
            DROPDOWN_WEIGHT_COL, DROPDOWN_GRADE_COL, DROPDOWN_ORIGIN_COL,
            DROPDOWN_J_COL, DROPDOWN_CATEGORY_COL,
        )
    }

    valid_positions = _existing_position_ids()
    now = datetime.now().isoformat(timespec="seconds")
    rows_to_insert = []
    used_positions = set()

    for row_num, row in df.iterrows():
        coil_id = _clean(row.get(coil_id_col))
        if coil_id is None:
            continue
        coil_id = str(coil_id).strip()
        if not coil_id:
            continue

        column_num = _clean(row.get(map_column_col)) if map_column_col else None
        position_raw = _clean(row.get(position_col)) if position_col else None
        position_id = _build_position_id(column_num, position_raw)

        if position_id is None:
            result.skipped += 1
            result.errors.append(
                f"Row {row_num + 2}: coil {coil_id} - could not parse column/position "
                f"(map column={column_num!r}, position={position_raw!r})."
            )
            continue

        if position_id not in valid_positions:
            result.skipped += 1
            result.errors.append(
                f"Row {row_num + 2}: coil {coil_id} - position {position_id} does not "
                f"exist in Area 1's layout."
            )
            continue

        if position_id in used_positions:
            # The real sheet currently has duplicate positions in places;
            # for now we only keep the first coil claiming a given
            # position and skip the rest, rather than stacking multiple
            # coils on top of each other on the map.
            result.skipped += 1
            result.errors.append(
                f"Row {row_num + 2}: coil {coil_id} - position {position_id} is already "
                f"taken by another coil in this import; skipped as a duplicate."
            )
            continue
        used_positions.add(position_id)

        lock_val = _clean(row.get(lock_col)) if lock_col else None
        locked = 1 if (lock_val is not None and str(lock_val).strip().upper() == "Y") else 0

        extra = {}
        for col in extra_cols:
            val = _clean(row.get(col))
            if val is not None:
                extra[str(col)] = val

        dropdown_label = _build_dropdown_label(coil_id, row, dropdown_letter_cols)

        rows_to_insert.append((coil_id, position_id, locked, json.dumps(extra, default=str), dropdown_label, now))

    if not rows_to_insert:
        result.errors.append("No valid coil rows found to import.")
        return result

    with get_cursor(commit=True) as cur:
        if replace_existing:
            clear_all_coils(cur)

        for coil_id, position_id, locked, extra_json, dropdown_label, ts in rows_to_insert:
            cur.execute(
                """
                INSERT INTO coils (coil_id, material, weight_kg, width_mm, status,
                                    current_position, previous_position, tag_id,
                                    last_movement, last_seen, location_confidence,
                                    extra_fields, locked, dropdown_label)
                VALUES (?, '', 0, 0, ?, ?, NULL, NULL, NULL, ?, NULL, ?, ?, ?)
                ON CONFLICT(coil_id) DO UPDATE SET
                    current_position = excluded.current_position,
                    extra_fields = excluded.extra_fields,
                    locked = excluded.locked,
                    last_seen = excluded.last_seen,
                    dropdown_label = excluded.dropdown_label
                """,
                (coil_id, config.COIL_STATUS_STATIONARY, position_id, ts, extra_json, locked, dropdown_label),
            )
            result.imported += 1

    return result
