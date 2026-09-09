# Steel Coil Warehouse Tracking — Milestone 1 (Software Simulation Prototype)

A Streamlit application that simulates live steel-coil tracking inside a
warehouse, so the user experience, warehouse layout, and movement logic can
be validated **before** any BLE hardware (tags, ESP32 receivers, MQTT) is
purchased or installed.

Everything hardware-related in this prototype is simulated in software:
coil positions, BLE tag assignment, movements, and RSSI readings.

## 1. Project structure

```
coil_tracking/
│
├── app.py                     # Entry point: KPIs + landing dashboard, DB init
├── requirements.txt
├── README.md
├── config.py                  # Warehouse layout, statuses, simulation constants
│
├── backend/
│   ├── database.py            # SQLite connection + schema + demo-data seeding
│   ├── models.py               # Data-access helpers for coils/tags/positions/movements
│   ├── simulation.py           # Movement simulation engine (MOVING -> STATIONARY)
│   ├── positioning.py          # Simulated confidence % and simulated RSSI
│   ├── tag_manager.py          # BLE tag lifecycle (assign/release/reuse) + production
│   └── warehouse_map.py        # Plotly figure builder for the warehouse map
│
├── pages/
│   ├── 1_Live_Map.py           # Live Warehouse Map (auto-refreshing)
│   ├── 2_Locate_Coil.py        # Search + highlight a coil
│   ├── 3_Simulation_Control.py # Manual + quick-action movement simulation
│   ├── 4_Movement_History.py   # Full movement audit trail with filters
│   ├── 5_Tag_Management.py     # Tag pool, coil creation, send-to-production
│   └── 6_System_Debug.py       # Simulated per-receiver RSSI viewer
│
├── data/
│   └── warehouse.db            # Created automatically on first run (SQLite)
│
└── assets/                     # Reserved for future layout/background assets
```

## 2. How it works

- **Area 1** is modeled as a 20m x 10m space with 5 columns (A–E), each
  with 15 ground positions (`A1`…`A15`, etc.) — 75 ground positions total.
- Between every pair of neighboring ground positions in a column there is
  an **upper position**, named e.g. `A1_2_UPPER` — 70 upper positions total.
  That's 145 logical positions in Area 1, all pre-generated into the
  `positions` table with real x/y coordinates so the map can place them
  correctly.
- **20 trial coils** (`C0001`…`C0020`) are seeded on startup with random
  realistic materials, weights (4,000–12,000 kg) and widths, each holding
  one of **20 reusable BLE tags** (`TAG-001`…`TAG-020`).
- The **Simulation Control** page lets you manually move any coil from its
  current position to any empty position. The engine sets the coil to
  `MOVING`, waits briefly (simulated travel time), then sets it back to
  `STATIONARY`, updates `previous_position`/`current_position`, generates a
  simulated location confidence (65–98%), and writes a row to the
  `movements` audit table. Quick buttons and a "5 random movements" button
  are provided for fast demos.
- The **Live Warehouse Map** page uses `st.fragment(run_every=...)` to
  auto-refresh every few seconds, so any movement triggered elsewhere (or
  by another browser tab) shows up without a manual reload.
- **Tag Management** models the real-world magnetic-holder tag lifecycle:
  a tag is `AVAILABLE` or `IN_USE`. Sending a coil to production clears its
  position, frees its tag for reuse, and keeps its full movement history
  intact.
- **System Debug** simulates RSSI (in dBm) from 10 virtual receivers
  (`RX1`…`RX10`) placed around Area 1, using a simple distance-based model
  with noise — a stand-in for the real ESP32/BLE signal data that will
  arrive later.

### Database

SQLite is used for zero-setup local development (`data/warehouse.db`,
created and seeded automatically on first run). All SQL lives in
`backend/database.py`; every other module goes through `backend/models.py`,
`backend/tag_manager.py`, or `backend/simulation.py`. To migrate to
PostgreSQL later, only `backend/database.py` needs to change (swap the
`sqlite3` connection/schema for `psycopg2`/SQLAlchemy) — no page or other
backend module touches SQL directly.

## 3. Install and run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The database is created and seeded automatically — no manual setup step is
required. Open the local URL Streamlit prints (typically
`http://localhost:8501`).

## 4. What controls the warehouse layout?

`config.py` — column names, slots per column, area dimensions, column
y-coordinates, upper-position offset, and virtual receiver placement all
live there. `backend/database.py::_seed_positions()` uses those constants
to generate every position row (with x/y) on first run. `backend/warehouse_map.py`
turns the `positions` + `coils` tables into the Plotly figure shown on the
Live Map and Locate Coil pages.

## 5. What controls simulated coil movement?

`backend/simulation.py` — `move_coil()` is the core function (sets
`MOVING`, simulates travel time, sets `STATIONARY`, updates positions,
generates confidence, logs to `movements`). `move_random_coil()` and
`simulate_n_random_movements()` back the quick-action buttons on the
**Simulation Control** page (`pages/3_Simulation_Control.py`).

## 6. Where should real MQTT / ESP32 integration be added?

- `backend/positioning.py::ingest_gateway_message()` is the placeholder
  entry point for real gateway messages, shaped like:

  ```json
  {
    "gateway_id": "AREA1_RX03",
    "tag_id": "TAG-037",
    "rssi": -61,
    "timestamp": "2026-09-09T16:34:12"
  }
  ```

  This is where an MQTT subscriber (e.g. an `paho-mqtt` client listening to
  a Mosquitto broker) would forward each ESP32 gateway message, feeding a
  real positioning/trilateration algorithm instead of
  `simulate_rssi_for_position()` / `generate_confidence()`.
- `backend/database.py` is where SQLite would be swapped for PostgreSQL.
- No Streamlit page talks to SQL or to a "receiver" directly — they all go
  through `backend/models.py`, `backend/simulation.py`, and
  `backend/positioning.py`, so hardware ingestion can be dropped in behind
  those same functions without touching the UI.
