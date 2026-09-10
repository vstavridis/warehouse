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
│   ├── warehouse_map.py        # Plotly figure builder for the warehouse map
│   ├── ui.py                   # Shared page chrome: hides the sidebar, renders the nav row
│   └── stock_import.py         # Parses the real stock-list Excel export into coils
│
├── pages/
│   ├── 1_Live_Map.py           # Live Warehouse Map (auto-refreshing) + coil search/locate
│   ├── 2_Simulation_Control.py # Manual + quick-action movement simulation
│   ├── 3_Movement_History.py   # Full movement audit trail with filters
│   ├── 4_Tag_Management.py     # Tag pool, coil creation, send-to-production
│   ├── 5_System_Debug.py       # Simulated per-receiver RSSI viewer
│   └── 6_Import_Stock.py       # Upload the stock-list Excel file to load real coils
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
- **20 trial coils** (`C0001`…`C0020`) are seeded on startup with realistic
  materials, weights (4,000–12,000 kg) and widths, each holding one of
  **20 reusable BLE tags** (`TAG-001`…`TAG-020`). The initial layout is
  generated from a fixed seed (`config.DEMO_SEED`), so a fresh database
  (e.g. after a restart on a host with an ephemeral filesystem) always
  starts with the same coil positions/materials instead of reshuffling on
  every reboot. Movements simulated afterward via Simulation Control are
  reseeded from OS entropy, so they stay unpredictable.
- The **Simulation Control** page lets you manually move any coil from its
  current position to any empty position. The engine sets the coil to
  `MOVING`, waits briefly (simulated travel time), then sets it back to
  `STATIONARY`, updates `previous_position`/`current_position`, generates a
  simulated location confidence (65–98%), and writes a row to the
  `movements` audit table. Quick buttons and a "5 random movements" button
  are provided for fast demos.
- The **Live Warehouse Map** page uses `st.fragment(run_every=...)` to
  auto-refresh every few seconds, so any movement triggered elsewhere (or
  by another browser tab) shows up without a manual reload. It renders as
  a large (760px), full-width floor plan — a dark building shell around a
  concrete-toned floor, shaded storage lanes per column, and dashed aisle
  markings between them — with no legend or axis scale drawn on the chart
  itself, styled to read like an actual warehouse layout rather than an
  abstract chart.
- Every occupied position renders a small metallic coil icon (layered wind
  lines around a dark bore, a cast shadow, and a specular highlight)
  instead of a plain shape. A plain stationary coil stays neutral metal;
  only the moving/missing states bake a colored ring into the icon, so the
  floor isn't awash in color for the common case. Upper-level coils render
  smaller.
- Search lives in a box **above** the map: type or pick a coil ID from the
  dropdown to highlight it there with a bright green ring. **Clicking a
  coil directly on the map** does the same highlighting *and* opens a
  popup (`st.dialog`) with its full detail panel (position, tag,
  confidence, extra stock-list fields, etc.) - there is no separate
  "Locate Coil" page and no inline panel taking up space on the page.
  Re-clicking the same coil reopens the popup every time (the chart
  widget is given a fresh key after each click, since Streamlit/Plotly
  otherwise treats a second click on an already-selected point as a
  deselect rather than a new click).
- There is no sidebar - `backend/ui.py` hides Streamlit's default page nav
  and instead renders a row of navigation buttons (`st.page_link`) at the
  top of every page, plus a dedicated Simulation/Movement/Management/Debug
  row below the map on the Live Map page itself.
- ⚠️ The Plotly chart's own "Fullscreen" button (bottom-right of its
  toolbar) uses the browser's native Fullscreen API on the chart's DOM
  node. Background auto-refreshes do not reliably repaint that element
  while it's in native fullscreen - a known interaction issue between
  Streamlit/Plotly and the Fullscreen API, not something fixable from
  application code. Rather than leave that trap in place, `backend/ui.py`
  hides the fullscreen button entirely; the map is sized large by default
  so it isn't needed.
- **Tag Management** models the real-world magnetic-holder tag lifecycle:
  a tag is `AVAILABLE` or `IN_USE`. Sending a coil to production clears its
  position, frees its tag for reuse, and keeps its full movement history
  intact.
- **System Debug** simulates RSSI (in dBm) from 10 virtual receivers
  (`RX1`…`RX10`) placed around Area 1, using a simple distance-based model
  with noise — a stand-in for the real ESP32/BLE signal data that will
  arrive later.
- **Import Stock** loads the real coil stock list from an exported Excel
  workbook (upload it directly - the app has no network access to fetch
  it from anywhere itself). It reads sheet `ΑΠΟΘΗΚΗ`, using row 1 as
  headers and ignoring the last (sums) row:
  - **Column F** — unique coil id
  - **Column I** — map column, `1`→A … `5`→E (anything else is skipped)
  - **Column H** — position within the column: a single number is a
    ground position (`5` → `D5`); a pair (`4,5`, `4-5`, or a value like
    `4.5`) is an upper position (`B4_5_UPPER`)
  - **Column Q** — `Y` marks the coil as locked, shown with a red 🔒 next
    to its id in the details popup
  - **Columns A, B, C, D, E, G, K, P, R** — free-form details shown in the
    popup, each labeled with that column's own row-1 header text (so a
    "K" column headed `ΚΑΤΗΓΟΡΙΑ` renders as `ΚΑΤΗΓΟΡΙΑ: <value>`)

  Material/weight are not part of this real data model, so the details
  popup no longer shows them at all (for any coil, including the
  simulated demo ones). Importing replaces every existing coil by default
  (a checkbox on the page allows an additive import instead); movement
  history is left untouched either way.

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
turns the `positions` + `coils` tables into the Plotly figure (including the
coil icon and status halos) shown on the Live Map page.

## 5. What controls simulated coil movement?

`backend/simulation.py` — `move_coil()` is the core function (sets
`MOVING`, simulates travel time, sets `STATIONARY`, updates positions,
generates confidence, logs to `movements`). `move_random_coil()` and
`simulate_n_random_movements()` back the quick-action buttons on the
**Simulation Control** page (`pages/2_Simulation_Control.py`).

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
