"""
Positioning engine (simulated).

This module isolates everything related to turning raw "signal" data into
a location + confidence score. Today the signal data is randomly
generated. Later, this is the module that will be replaced/extended to
consume real ESP32 gateway messages of the form:

    {
        "gateway_id": "AREA1_RX03",
        "tag_id": "TAG-037",
        "rssi": -61,
        "timestamp": "2026-09-09T16:34:12"
    }

and run a real trilateration / fingerprinting algorithm instead of the
random simulation below. Nothing in the Streamlit pages depends on how
this module computes its numbers - they only call the functions here.
"""

import math
import random
from typing import Dict

import config
from backend import models


def generate_confidence() -> float:
    """Simulate a realistic BLE location confidence percentage."""
    return round(random.uniform(config.CONFIDENCE_MIN, config.CONFIDENCE_MAX), 1)


def is_low_confidence(confidence: float) -> bool:
    return confidence is not None and confidence < config.LOW_CONFIDENCE_THRESHOLD


def simulate_rssi_for_position(position_id: str) -> Dict[str, int]:
    """Simulate an RSSI reading (in dBm) from every virtual receiver for a
    coil sitting at the given position. Closer receivers report a
    stronger (less negative) signal, with random noise added to mimic a
    real BLE environment.
    """
    position = models.get_position(position_id)
    readings = {}

    for rx_id, rx in config.RECEIVERS.items():
        if position:
            distance = math.hypot(position["x"] - rx["x"], position["y"] - rx["y"])
        else:
            distance = random.uniform(1, 25)

        # Simple free-space-ish path loss model just for realistic-looking demo numbers.
        base_rssi = -40 - 20 * math.log10(max(distance, 0.5))
        noise = random.uniform(-4, 4)
        rssi = round(base_rssi + noise)
        readings[rx_id] = max(min(rssi, -30), -100)

    return readings


def ingest_gateway_message(message: dict) -> None:
    """Placeholder entry point for future real hardware ingestion.

    A real ESP32 gateway will eventually POST/publish (via MQTT) messages
    shaped like:
        {"gateway_id": "AREA1_RX03", "tag_id": "TAG-037",
         "rssi": -61, "timestamp": "..."}

    This function is where that raw signal would be fed into a real
    positioning algorithm to compute current_position + confidence for
    the coil wearing that tag, then persist it via backend.models. It is
    intentionally unused by the simulation UI today.
    """
    raise NotImplementedError(
        "Hardware ingestion is not implemented in the simulation prototype. "
        "This is the integration point for real MQTT/ESP32 data."
    )
