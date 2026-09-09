"""
BLE tag lifecycle management.

In the real system, a BLE tag is physically attached to a coil with a
magnetic holder and is reused once that coil is consumed in production.
This module models that lifecycle: a tag is either AVAILABLE (sitting in
the tag pool, not attached to anything) or IN_USE (attached to a coil).
"""

from typing import Optional

import config
from backend.database import get_cursor
from backend import models


class TagError(Exception):
    pass


def assign_tag(tag_id: str, coil_id: str) -> None:
    tag = models.get_tag(tag_id)
    if tag is None:
        raise TagError(f"Tag {tag_id} does not exist.")
    if tag["status"] == config.TAG_STATUS_IN_USE:
        raise TagError(f"Tag {tag_id} is already in use by coil {tag['coil_id']}.")

    coil = models.get_coil(coil_id)
    if coil is None:
        raise TagError(f"Coil {coil_id} does not exist.")

    with get_cursor(commit=True) as cur:
        # Release whatever tag the coil currently has, if any
        if coil.get("tag_id"):
            cur.execute(
                "UPDATE tags SET status = ?, coil_id = NULL WHERE tag_id = ?",
                (config.TAG_STATUS_AVAILABLE, coil["tag_id"]),
            )
        cur.execute(
            "UPDATE tags SET status = ?, coil_id = ? WHERE tag_id = ?",
            (config.TAG_STATUS_IN_USE, coil_id, tag_id),
        )
        cur.execute("UPDATE coils SET tag_id = ? WHERE coil_id = ?", (tag_id, coil_id))


def release_tag(tag_id: str) -> None:
    tag = models.get_tag(tag_id)
    if tag is None:
        raise TagError(f"Tag {tag_id} does not exist.")

    with get_cursor(commit=True) as cur:
        if tag["coil_id"]:
            cur.execute("UPDATE coils SET tag_id = NULL WHERE coil_id = ?", (tag["coil_id"],))
        cur.execute(
            "UPDATE tags SET status = ?, coil_id = NULL WHERE tag_id = ?",
            (config.TAG_STATUS_AVAILABLE, tag_id),
        )


def send_to_production(coil_id: str) -> None:
    """Coil leaves the warehouse for production: it is removed from the
    floor, its tag becomes available again for reuse, and its movement
    history is preserved untouched."""
    coil = models.get_coil(coil_id)
    if coil is None:
        raise TagError(f"Coil {coil_id} does not exist.")

    old_position = coil["current_position"]
    tag_id = coil["tag_id"]

    models.add_movement(
        coil_id=coil_id,
        tag_id=tag_id,
        from_position=old_position,
        to_position=None,
        movement_type=config.MOVEMENT_TYPE_PRODUCTION,
        confidence=None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            UPDATE coils
            SET status = ?, current_position = NULL, previous_position = ?,
                tag_id = NULL, last_movement = datetime('now')
            WHERE coil_id = ?
            """,
            (config.COIL_STATUS_PRODUCTION, old_position, coil_id),
        )
        if tag_id:
            cur.execute(
                "UPDATE tags SET status = ?, coil_id = NULL WHERE tag_id = ?",
                (config.TAG_STATUS_AVAILABLE, tag_id),
            )
