"""
Import the "Έτοιμα προϊόντα" (ready products) sheet from a second OneDrive
workbook - a separate file from the main ΑΠΟΘΗΚΗ stock list, read from the
same OneDrive account (see backend/onedrive.py), used only by the Optimize
(truck loading) page.

Column matching follows the same header-name-first approach as
backend/stock_import.py, with the column letters from the reference
screenshot (A..P) as a fallback for a sheet whose headers don't match any
known spelling.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
from openpyxl.utils import column_index_from_string

from backend.database import get_cursor
from backend.stock_import import normalize_key, _resolve_column, _letter_column, _clean

SHEET_NAME = "Έτοιμα προϊόντα"
SHEET_NAME_CANDIDATES = [
    "Έτοιμα προϊόντα", "ΕΤΟΙΜΑ ΠΡΟΪΟΝΤΑ", "Ετοιμα προϊοντα", "ΕΤΟΙΜΑ ΠΡΟΙΟΝΤΑ",
    "Ετοιμα Προιοντα", "ready products", "finished products",
]


def _resolve_sheet_name_from_xls(xls) -> tuple:
    """Returns (resolved_sheet_name, available_sheet_names). Matches by
    normalized text (accent/case/space-insensitive) rather than requiring
    an exact string match, since a real workbook's sheet name easily
    differs from this app's own guess by a stray space, a missing tonos
    accent, or different capitalization."""
    available = xls.sheet_names
    normalized_lookup = {normalize_key(name): name for name in available}
    for candidate in SHEET_NAME_CANDIDATES:
        match = normalized_lookup.get(normalize_key(candidate))
        if match:
            return match, available
    return None, available

# header-name candidates -> (db column, fallback letter)
FIELD_MAP = [
    ("eidos", ["ΕΙΔΟΣ"], "A"),
    ("paxos", ["ΠΑΧΟΣ"], "B"),
    ("diastaseis", ["ΔΙΑΣΤΑΣΕΙΣ"], "C"),
    ("temaxia", ["ΤΕΜΑΧΙΑ"], "D"),
    ("kila", ["ΚΙΛΑ"], "E"),
    ("pelatis", ["ΠΕΛΑΤΗΣ"], "F"),
    ("vs_pg", ["VS/PG", "VS PG"], "G"),
    ("barcode", ["BARCODE"], "H"),
    ("topothesia", ["ΤΟΠΟΘΕΣΙΑ"], "I"),
    ("thesi", ["ΘΕΣΗ"], "J"),
    ("rolo", ["ΡΟΛΟ"], "K"),
    ("poiotita", ["ΠΟΙΟΤΗΤΑ"], "L"),
    ("xora", ["ΧΩΡΑ"], "M"),
    ("ext_id", ["ID"], "N"),
    ("kostos", ["ΚΟΣΤΟΣ"], "O"),
    ("imerominia", ["ΗΜΕΡΟΜΗΝΙΑ"], "P"),
]


@dataclass
class ReadyProductsImportResult:
    imported: int = 0
    errors: list = field(default_factory=list)
    matched_columns: dict = field(default_factory=dict)


def _to_number(value) -> Optional[float]:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def import_ready_products_from_excel(file) -> ReadyProductsImportResult:
    result = ReadyProductsImportResult()

    try:
        xls = pd.ExcelFile(file, engine="openpyxl")
    except Exception as e:
        result.errors.append(f"Could not open workbook: {e}")
        return result

    resolved_name, available = _resolve_sheet_name_from_xls(xls)
    if resolved_name is None:
        result.errors.append(
            f"Could not find a '{SHEET_NAME}' sheet in this workbook. "
            f"Sheets found: {', '.join(available) if available else '(none)'}."
        )
        return result

    try:
        df = xls.parse(sheet_name=resolved_name, header=0)
    except Exception as e:
        result.errors.append(f"Could not read sheet '{resolved_name}': {e}")
        return result

    if df.empty:
        result.errors.append(f"Sheet '{resolved_name}' is empty.")
        return result

    resolved = {}
    for db_col, candidates, fallback_letter in FIELD_MAP:
        col = _resolve_column(df.columns, candidates) or _letter_column(df, fallback_letter)
        resolved[db_col] = col
        result.matched_columns[candidates[0]] = col

    rows_to_insert = []
    for _, row in df.iterrows():
        values = {}
        for db_col, _candidates, _letter in FIELD_MAP:
            col = resolved[db_col]
            raw = row.get(col) if col is not None else None
            values[db_col] = raw

        # Skip fully blank rows (e.g. a trailing sums/blank row).
        if all(_clean(v) is None for v in values.values()):
            continue

        rows_to_insert.append((
            _clean(values["eidos"]),
            _clean(values["paxos"]),
            _clean(values["diastaseis"]),
            _to_number(values["temaxia"]),
            _to_number(values["kila"]),
            _clean(values["pelatis"]),
            _clean(values["vs_pg"]),
            _clean(values["barcode"]),
            _clean(values["topothesia"]),
            _clean(values["thesi"]),
            _clean(values["rolo"]),
            _clean(values["poiotita"]),
            _clean(values["xora"]),
            _clean(values["ext_id"]),
            _to_number(values["kostos"]),
            str(_clean(values["imerominia"])) if _clean(values["imerominia"]) is not None else None,
        ))

    if not rows_to_insert:
        result.errors.append("No data rows found to import.")
        return result

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM ready_products")
        cur.executemany(
            """
            INSERT INTO ready_products (
                eidos, paxos, diastaseis, temaxia, kila, pelatis, vs_pg,
                barcode, topothesia, thesi, rolo, poiotita, xora, ext_id,
                kostos, imerominia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
    result.imported = len(rows_to_insert)
    return result
