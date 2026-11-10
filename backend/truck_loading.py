"""
Truck-loading optimizer for the Optimize page.

Turns a list of selected "ready product" rows (ΔΙΑΣΤΑΣΕΙΣ + ΚΙΛΑ) into a
3D loading plan for a standard semi-trailer (config.TRUCK_* constants),
respecting:

  - max total weight (config.TRUCK_MAX_WEIGHT_KG)
  - max width/length per row of pallets (config.TRUCK_WIDTH_MM / _LENGTH_MM)
  - coils and strips can never be stacked; sheets can, up to
    config.SHEET_MAX_STACK (bounded further by truck height)
  - sheet pallets keep their own real footprint (from ΔΙΑΣΤΑΣΕΙΣ, e.g.
    "900X500"); coil/strip pallets use the fixed square footprints every
    coil/strip pallet in this warehouse actually uses

Front-to-back weight balance: with no axle-position data to work from,
the heuristic used here is to keep the trailer's two length-halves as
close in total weight as possible (process heaviest rows first, always
assigning the next row to whichever half currently carries less weight,
building front-to-back and back-to-front at the same time) rather than
piling every heavy row at one end - a reasonable stand-in for "don't
overload one axle group" without real axle-position data to optimize
against directly. Left-right balance within a row comes for free by
always centering each row's pallets across the trailer's width.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import config


# ---------------------------------------------------------------------------
# Step 1: classify a ΔΙΑΣΤΑΣΕΙΣ string into a pallet footprint
# ---------------------------------------------------------------------------
_ROLL_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*XΡΟΛΟ$")
_SHEET_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)$")


def classify_dimension(raw) -> Optional[dict]:
    """Returns a dict describing the physical pallet for this ΔΙΑΣΤΑΣΕΙΣ
    value, or None if it doesn't match either known format (a "roll"
    width like "180ΧΡΟΛΟ", or a plain "WIDTHxLENGTH" like "900X500" -
    everything in mm already, per this warehouse's own convention)."""
    if raw is None:
        return None
    s = str(raw).strip().upper().replace("Χ", "X").replace(",", ".")
    if not s:
        return None

    m = _ROLL_RE.match(s)
    if m:
        roll_width = float(m.group(1))
        if roll_width >= config.COIL_ROLL_WIDTH_THRESHOLD_MM:
            return {
                "kind": "coil",
                "width_mm": float(config.COIL_PALLET_SIZE_MM),
                "length_mm": float(config.COIL_PALLET_SIZE_MM),
                "height_mm": float(config.COIL_PALLET_HEIGHT_MM),
                "stackable": False,
            }
        return {
            "kind": "strips",
            "width_mm": float(config.STRIP_PALLET_SIZE_MM),
            "length_mm": float(config.STRIP_PALLET_SIZE_MM),
            "height_mm": float(config.STRIP_PALLET_HEIGHT_MM),
            "stackable": False,
        }

    m = _SHEET_RE.match(s)
    if m:
        width, length = float(m.group(1)), float(m.group(2))
        return {
            "kind": "sheet",
            "width_mm": width,
            "length_mm": length,
            "height_mm": float(config.SHEET_PALLET_HEIGHT_MM),
            "stackable": True,
        }
    return None


# ---------------------------------------------------------------------------
# Step 2: selected rows -> individual Pallet objects
# ---------------------------------------------------------------------------
@dataclass
class Pallet:
    id: str
    kind: str  # "coil" | "strips" | "sheet"
    width_mm: float
    length_mm: float
    height_mm: float
    weight_kg: float
    label: str
    stackable: bool


def build_pallets(selected_rows: list) -> tuple:
    """selected_rows: list of dicts with at least 'row_id', 'eidos',
    'diastaseis', 'kila'. Returns (pallets, warnings)."""
    pallets, warnings = [], []
    for row in selected_rows:
        dims = classify_dimension(row.get("diastaseis"))
        if dims is None:
            warnings.append(
                f"Row {row.get('row_id')}: could not classify ΔΙΑΣΤΑΣΕΙΣ "
                f"{row.get('diastaseis')!r} (expected e.g. \"180ΧΡΟΛΟ\" or "
                f"\"900X500\") - skipped."
            )
            continue
        weight = row.get("kila")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 0.0
        label = str(row.get("eidos") or "").strip() or str(row.get("diastaseis") or "")
        pallets.append(Pallet(
            id=str(row.get("row_id")), kind=dims["kind"],
            width_mm=dims["width_mm"], length_mm=dims["length_mm"],
            height_mm=dims["height_mm"], weight_kg=weight, label=label,
            stackable=dims["stackable"],
        ))
    return pallets, warnings


# ---------------------------------------------------------------------------
# Step 3: group sheet pallets into stacks (coils/strips never stack)
# ---------------------------------------------------------------------------
def _build_units(pallets: list) -> list:
    """Returns a list of "load units" - a unit is either a single
    coil/strips pallet, or a stack of 1+ sheet pallets sharing the same
    footprint. Each unit is a dict with width_mm/length_mm/height_mm/
    weight_kg/kind/label/pallet_ids/members (members only set for sheet
    stacks, used later to draw each physical pallet layer in the 3D view)."""
    units = []

    non_sheets = [p for p in pallets if not p.stackable]
    for p in non_sheets:
        units.append({
            "kind": p.kind, "width_mm": p.width_mm, "length_mm": p.length_mm,
            "height_mm": p.height_mm, "weight_kg": p.weight_kg,
            "label": p.label, "pallet_ids": [p.id], "members": None,
        })

    sheets = [p for p in pallets if p.stackable]
    groups = defaultdict(list)
    for p in sheets:
        groups[(round(p.width_mm), round(p.length_mm))].append(p)

    for (w, l), items in groups.items():
        items = sorted(items, key=lambda p: -p.weight_kg)
        unit_height = items[0].height_mm
        max_by_height = max(1, int(config.TRUCK_HEIGHT_MM // unit_height))
        max_stack = max(1, min(config.SHEET_MAX_STACK, max_by_height))
        for i in range(0, len(items), max_stack):
            chunk = items[i:i + max_stack]
            label = chunk[0].label
            if len(chunk) > 1:
                label = f"{label} (x{len(chunk)} stacked)"
            units.append({
                "kind": "sheet", "width_mm": float(w), "length_mm": float(l),
                "height_mm": unit_height * len(chunk),
                "weight_kg": sum(c.weight_kg for c in chunk),
                "label": label, "pallet_ids": [c.id for c in chunk],
                "members": chunk,
            })

    return units


# ---------------------------------------------------------------------------
# Step 4: shelf-pack units into rows across the truck's width
# ---------------------------------------------------------------------------
def _build_rows(units: list) -> tuple:
    """Groups units sharing an identical footprint/height into rows that
    fit side-by-side across the truck's width (config.TRUCK_WIDTH_MM).
    Returns (rows, unfit_units) - a unit that doesn't fit the truck's
    width even rotated (sheets only; coil/strip pallets are square) is
    reported as unfit rather than silently dropped."""
    groups = defaultdict(list)
    for u in units:
        groups[(u["kind"], round(u["width_mm"]), round(u["length_mm"]), round(u["height_mm"]))].append(u)

    rows, unfit = [], []
    for (kind, w, l, h), items in groups.items():
        width_mm, length_mm = float(w), float(l)
        cols = int(config.TRUCK_WIDTH_MM // width_mm)
        if cols < 1 and kind == "sheet":
            # Try the pallet rotated 90 degrees (long side across the
            # truck) before giving up on it entirely.
            width_mm, length_mm = length_mm, width_mm
            cols = int(config.TRUCK_WIDTH_MM // width_mm)
        if cols < 1 or length_mm > config.TRUCK_LENGTH_MM:
            unfit.extend(items)
            continue
        for i in range(0, len(items), cols):
            chunk = items[i:i + cols]
            rows.append({
                "kind": kind, "item_width_mm": width_mm, "item_length_mm": length_mm,
                "item_height_mm": float(h), "items": chunk,
                "row_weight_kg": sum(it["weight_kg"] for it in chunk),
            })
    return rows, unfit


# ---------------------------------------------------------------------------
# Step 5: place rows front-to-back, balancing weight, within max tonnage
# ---------------------------------------------------------------------------
@dataclass
class Placement:
    x_mm: float
    y_mm: float
    z_mm: float
    width_mm: float
    length_mm: float
    height_mm: float
    weight_kg: float
    kind: str
    label: str
    pallet_ids: list
    members: Optional[list] = None


@dataclass
class PackingResult:
    placements: list = field(default_factory=list)
    total_weight_kg: float = 0.0
    used_length_mm: float = 0.0
    warnings: list = field(default_factory=list)


def pack_pallets(selected_rows: list) -> PackingResult:
    result = PackingResult()

    pallets, warnings = build_pallets(selected_rows)
    result.warnings.extend(warnings)
    if not pallets:
        return result

    units = _build_units(pallets)
    rows, unfit_units = _build_rows(units)
    for u in unfit_units:
        result.warnings.append(
            f"{u['label']}: pallet {u['width_mm']:.0f}x{u['length_mm']:.0f}mm "
            f"does not fit the truck's {config.TRUCK_WIDTH_MM}mm width - skipped."
        )

    rows_sorted = sorted(rows, key=lambda r: -r["row_weight_kg"])
    front_x, back_x = 0.0, float(config.TRUCK_LENGTH_MM)
    front_weight, back_weight, total_weight = 0.0, 0.0, 0.0

    for row in rows_sorted:
        length = row["item_length_mm"]
        if total_weight + row["row_weight_kg"] > config.TRUCK_MAX_WEIGHT_KG:
            result.warnings.append(
                f"{row['kind']} row ({row['row_weight_kg']:.0f} kg) skipped - would "
                f"exceed the truck's {config.TRUCK_MAX_WEIGHT_KG} kg max tonnage."
            )
            continue
        if front_x + length > back_x:
            result.warnings.append(
                f"{row['kind']} row skipped - not enough room left along the "
                f"truck's {config.TRUCK_LENGTH_MM}mm length."
            )
            continue

        if front_weight <= back_weight:
            row_x = front_x
            front_x += length
            front_weight += row["row_weight_kg"]
        else:
            back_x -= length
            row_x = back_x
            back_weight += row["row_weight_kg"]
        total_weight += row["row_weight_kg"]

        items = row["items"]
        used_width = row["item_width_mm"] * len(items)
        start_y = (config.TRUCK_WIDTH_MM - used_width) / 2.0
        for idx, unit in enumerate(items):
            result.placements.append(Placement(
                x_mm=row_x, y_mm=start_y + idx * row["item_width_mm"], z_mm=0.0,
                width_mm=row["item_width_mm"], length_mm=row["item_length_mm"],
                height_mm=row["item_height_mm"], weight_kg=unit["weight_kg"],
                kind=unit["kind"], label=unit["label"],
                pallet_ids=unit["pallet_ids"], members=unit["members"],
            ))

    result.total_weight_kg = total_weight
    # Pallets are loaded from both ends inward (see module docstring), so
    # the truck's occupied length is the front section plus the back
    # section, not just whichever single section is longer.
    result.used_length_mm = front_x + (config.TRUCK_LENGTH_MM - back_x)
    return result
