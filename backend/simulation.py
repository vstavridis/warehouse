"""
Movement simulation engine.

This is where "hardware" is simulated for Milestone 1. A real system would
detect movement from BLE RSSI changes across ESP32 gateways; here we just
let the operator (or a quick-action button) declare a movement and we walk
the coil through MOVING -> STATIONARY while recording history exactly the
same way a real detection pipeline would.
"""

import random
import time
from typing import Optional

import config
from backend import models
from backend.positioning import generate_confidence


class SimulationError(Exception):
    pass


def move_coil(coil_id: str, to_position: str, movement_type: str = config.MOVEMENT_TYPE_SIMULATED,
              animate: bool = True) -> dict:
    """Move a coil from its current position to a new position.

    Returns the confidence score generated for the completed movement.
    """
    coil = models.get_coil(coil_id)
    if coil is None:
        raise SimulationError(f"Coil {coil_id} does not exist.")

    target = models.get_position(to_position)
    if target is None:
        raise SimulationError(f"Position {to_position} does not exist.")

    occupied_by = _coil_at_position(to_position, exclude_coil_id=coil_id)
    if occupied_by:
        raise SimulationError(f"Position {to_position} is already occupied by {occupied_by}.")

    from_position = coil["current_position"]

    # Step 1: mark as moving so the live map reflects it immediately.
    models.update_coil(coil_id, status=config.COIL_STATUS_MOVING)

    if animate:
        time.sleep(config.MOVEMENT_TRAVEL_SECONDS)

    # Step 2: complete the movement.
    confidence = generate_confidence()
    models.update_coil(
        coil_id,
        status=config.COIL_STATUS_STATIONARY,
        current_position=to_position,
        previous_position=from_position,
        last_movement=_now(),
        last_seen=_now(),
        location_confidence=confidence,
    )

    models.add_movement(
        coil_id=coil_id,
        tag_id=coil["tag_id"],
        from_position=from_position,
        to_position=to_position,
        movement_type=movement_type,
        confidence=confidence,
    )

    return {"coil_id": coil_id, "from": from_position, "to": to_position, "confidence": confidence}


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _coil_at_position(position_id: str, exclude_coil_id: Optional[str] = None) -> Optional[str]:
    df = models.get_active_coils()
    if df.empty:
        return None
    matches = df[df["current_position"] == position_id]
    if exclude_coil_id:
        matches = matches[matches["coil_id"] != exclude_coil_id]
    if matches.empty:
        return None
    return matches.iloc[0]["coil_id"]


def move_random_coil(animate: bool = True) -> Optional[dict]:
    active = models.get_active_coils()
    stationary = active[active["status"] == config.COIL_STATUS_STATIONARY]
    if stationary.empty:
        return None

    empty_positions = models.get_empty_positions()
    if not empty_positions:
        return None

    coil_id = random.choice(stationary["coil_id"].tolist())
    to_position = random.choice(empty_positions)
    return move_coil(coil_id, to_position, animate=animate)


def simulate_n_random_movements(n: int = 5, animate: bool = False) -> list:
    results = []
    for _ in range(n):
        result = move_random_coil(animate=animate)
        if result:
            results.append(result)
    return results
