"""
Shared number formatting for stock-list values, used both when building
each coil's search-dropdown label at import time and when rendering the
details popup. Kept in one place so the two stay consistent.
"""

from typing import Optional


def format_thickness(value) -> str:
    """Thickness (ΠΑΧΟΣ) needs its real decimal precision preserved -
    rounding 0.50mm to a whole number would silently turn it into a
    different, wrong spec. Formatted with a comma decimal separator to
    match this warehouse's own convention (e.g. "0,50")."""
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def format_whole_number(value) -> str:
    """Most other numeric stock-list fields (weight, meters, price, width)
    are fine rounded to a whole number - Excel formula results often carry
    long floating-point tails (e.g. 609.7664543524415 for a meters
    column)."""
    if value is None:
        return ""
    try:
        return str(round(float(value)))
    except (TypeError, ValueError):
        return str(value)


def format_stock_value(label: Optional[str], value):
    """Format a labeled stock-list value for display: thickness keeps its
    decimal precision, everything else numeric rounds to a whole number,
    text passes through unchanged."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if label and label.strip().upper() == "ΠΑΧΟΣ":
        return format_thickness(value)
    return format_whole_number(value)
