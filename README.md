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
│   ├── ui.py                   # Shared page chrome: hides the sidebar, renders the nav row,
│   │                           # kicks off the OneDrive auto-sync check
│   ├── stock_import.py         # Parses the real stock-list Excel export into coils
│   ├── onedrive.py             # Microsoft Graph device-code auth + file download
│   ├── onedrive_sync.py        # Periodic "is a re-sync due?" check that triggers the import
│   ├── github_backup.py        # Backs up/restores the OneDrive connection via a GitHub repo
│   └── formatting.py           # Shared numeric formatting (thickness precision, etc.)
│
├── pages/
│   ├── 1_Live_Map.py           # Live Warehouse Map (auto-refreshing) + coil search/locate
│   ├── 2_Simulation_Control.py # Manual + quick-action movement simulation
│   ├── 3_Movement_History.py   # Full movement audit trail with filters
│   ├── 4_Tag_Management.py     # Tag pool, coil creation, send-to-production
│   ├── 5_System_Debug.py       # Simulated per-receiver RSSI viewer
│   └── 6_Import_Stock.py       # OneDrive auto-sync setup + manual stock file upload
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
  check for updates (every 12s by default - `config.LIVE_MAP_REFRESH_SECONDS`),
  so any movement triggered elsewhere (or by another browser tab) shows up
  without a manual reload. It renders as a large (760px), full-width floor
  plan — a dark building shell around a concrete-toned floor, shaded
  storage lanes per column, and dashed aisle markings between them — with
  no legend or axis scale drawn on the chart itself, styled to read like
  an actual warehouse layout rather than an abstract chart. The figure is
  only actually rebuilt and re-sent when something relevant changed
  (a coil's position/status/lock, or the current selection) - a hash of
  that state is cached in `st.session_state` and compared each tick, so
  an idle warehouse causes zero DOM updates in the chart instead of a
  full redraw every 12 seconds (verified with a `MutationObserver`: 0
  mutations on an unchanged tick, vs. several right after a real move).
- Every occupied position renders a small metallic coil icon (layered wind
  lines around a dark bore, a cast shadow, and a specular highlight)
  instead of a plain shape. A plain stationary coil stays neutral metal;
  only the moving/missing states bake a colored ring into the icon, so the
  floor isn't awash in color for the common case. Upper-level coils render
  smaller.
- Search lives in a box **above** the map: type or pick a coil ID from the
  dropdown to highlight it there with a bright green ring. **Clicking a
  coil directly on the map** does the same highlighting *and* opens a wide
  popup (`st.dialog(width="large")`) with its detail panel on the left and
  any stock-list fields on the right, separated by a vertical divider
  (scoped CSS on the dialog's second column) instead of stacking
  everything in one narrow, tall column - there is no separate "Locate
  Coil" page. Numeric stock-list values are rounded to whole numbers for
  display (Excel formula results often carry long floating-point tails,
  e.g. a meters column reading `609.7664543524415`).
  Re-clicking the same coil reopens the popup every time. This needs two
  deliberate workarounds: Plotly's click-to-select genuinely *toggles* -
  a second click on an already-selected point deselects it, reported as
  an empty event indistinguishable from "nothing happened" - so the page
  tracks the on/off *transition* itself and treats a deselect right after
  a select as "clicked again", reopening with the previously-selected
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
  Re-clicking the same coil reopens the popup every time. This needs two
  deliberate workarounds: Plotly's click-to-select genuinely *toggles* -
  a second click on an already-selected point deselects it, reported as
  an empty event indistinguishable from "nothing happened" - so the page
  tracks the on/off *transition* itself and treats a deselect right after
  a select as "clicked again", reopening with the previously-selected
  coil. Separately, dismissing the popup appears to remount the chart
  component, which replays its last selection as a phantom new event on
  the very next run; an `on_dismiss` callback flags that so the replay
  is absorbed instead of reopening the popup unprompted.
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
  workbook, either uploaded manually or **automatically synced from
  OneDrive** on a schedule (see below) so the stock list stays current
  without anyone re-uploading it. It reads sheet `ΑΠΟΘΗΚΗ`, using row 1 as
  headers and ignoring the last (sums) row. If two coils resolve to the
  same position, only the first one is kept and the rest are reported as
  skipped duplicates (the real sheet currently has some, and stacking
  multiple coils on one map position isn't useful — that's a data
  problem to resolve on the stock-list side later, not something to
  paper over here). Columns are matched **by
  header text** (accent/case/space-insensitive, with a few alternate
  spellings tried per field) rather than fixed column letters - the same
  technique this warehouse's existing stock-lookup ("Slitter") tool
  already uses successfully to read this exact sheet, so reordering or
  inserting columns in the file won't break the import:
  - **Coil id** — header `Νο ΡΟΛΛΟΥ` (falls back to column F if no header matches)
  - **Position** — header `ΘΕΣΗ` (falls back to column H): a single number
    is a ground position (`5` → `D5`); a pair (`4,5`, `4-5`, or a value
    like `4.5`) is an upper position (`B4_5_UPPER`)
  - **Map column** — column I, `1`→A … `5`→E (anything else is skipped);
    no header-name equivalent exists in the other stock tool, so this one
    is still letter-based
  - **Locked** — column Q, `Y` marks the coil as locked, shown with a red
    🔒 next to its id in the details popup; also still letter-based
  - **Details shown in the popup** — matched by header text where
    present: `ΕΙΔΟΣ`, `ΠΟΙΟΤΗΤΑ`, `ΠΑΧΟΣ`, `ΔΙΑΣΤΑΣΕΙΣ`/`ΠΛΑΤΟΣ`, `ΒΑΡΟΣ`,
    `ΜΕΤΡΑ`, `ΠΡΟΕΛΕΥΣΗ`, `ΤΟΜΕΑΣ`, `ΚΑΤΗΓΟΡΙΑ`, `ΤΙΜΗ`/`PRICE`,
    `ΠΕΡΙΓΡΑΦΗ`/`Description` — each rendered labeled with whichever of
    those header spellings is actually found; a field missing from the
    sheet is simply skipped. The Import Stock page shows exactly which
    real column was matched to each field after every import, so a
    mismatch is easy to spot.
  - **Search dropdown label** — built from fixed columns independent of
    the header-matching above (`backend/stock_import.py::_build_dropdown_label`):
    `<coil id (F)> / <material (A)> <thickness (B)> x <width (C)> - <weight (D)> / <grade (E)> / <origin (G)> / <col J> / <category (K)>`,
    e.g. `SID846713 / Galvanized 0,50 x 1000 - 9510 / DX51+Z140 / ΣΙΔΜΑ / 980 / A`.
    Stored per-coil at import time (`dropdown_label` column) so the Live
    Map search box doesn't need to recompute it on every rerun.

  Numeric values are formatted by `backend/formatting.py`, shared between
  the dropdown label and the details popup: **ΠΑΧΟΣ (thickness) always
  keeps its two-decimal precision** (comma separator, e.g. `0,50`) since
  rounding it to a whole number would silently turn it into a different,
  wrong spec — every other numeric field (weight, meters, price, width)
  rounds to a whole number, since those often carry long floating-point
  tails from Excel formulas (e.g. `609.7664543524415` → `610`).

  Material/weight are not part of this real data model, so the details
  popup no longer shows them at all (for any coil, including the
  simulated demo ones). Importing replaces every existing coil by default
  (a checkbox on the page allows an additive import instead); movement
  history is left untouched either way.

### OneDrive auto-sync

`backend/onedrive.py` implements Microsoft Graph's OAuth **device-code**
flow (no redirect URL to register - the user just visits a short
Microsoft URL once and enters a code), reusing the same public/non-secret
client id this warehouse's existing "Slitter" Streamlit app already uses
to read this exact OneDrive file, so no new Azure AD app registration is
needed. From the Import Stock page: "Connect with Microsoft" starts the
flow, then paste in the OneDrive link to the workbook, turn on
"Automatically re-sync on a schedule", and pick an interval. The
resulting refresh token and settings are stored in the `settings` table.

`backend/onedrive_sync.py::maybe_auto_sync()` runs from
`backend/ui.py::apply_page_chrome()` (called on every page), so it's a
cheap settings check on most page loads and only actually calls out to
OneDrive once the configured interval has elapsed. It compares the
file's `eTag` to skip re-importing when nothing has changed, and any
failure (network, auth, parsing) is recorded rather than raised, visible
on the Import Stock page instead of breaking the rest of the app.

⚠️ This was built and code-reviewed in a network-sandboxed dev
environment with no route to `graph.microsoft.com` or
`onedrive.live.com` (only `login.microsoftonline.com` was reachable,
enough to verify the device-code handshake itself is wired correctly) -
the actual file-download step needs to be verified once deployed
somewhere with normal internet access.

#### Surviving a reboot without reconnecting to Microsoft

The OneDrive refresh token lives in the `settings` table, so it survives
a reboot as long as the database itself does (see **Database** below) -
but a host with no writable persistent storage mount at all would lose it
on every redeploy, forcing a manual reconnect each time. To avoid that,
`backend/github_backup.py` mirrors this warehouse's existing "Slitter"
app's own GitHub-backup pattern: right after a successful "Connect with
Microsoft", the refresh token and sync settings are also written to a
small JSON file in a GitHub repo via the Contents API
(`warehouse_data/onedrive_settings.json`). On every page load,
`backend/onedrive_sync.py::maybe_auto_sync()` checks
`onedrive.is_connected()` first and, only if the local settings table has
no token at all (a fresh/reset container), restores it from that GitHub
backup before proceeding - it never overwrites a connection that's
already present locally.

This is opt-in and silent when unconfigured: nothing happens unless a
GitHub token and repo are set. To enable it, add these secrets/env vars
(checked in this order, so a deployment that already has Slitter's own
GitHub-backup secrets configured picks them up for free with no extra
setup):

```
WAREHOUSE_GITHUB_TOKEN   # a PAT with "repo" (or fine-grained "contents: write") access
WAREHOUSE_GITHUB_REPO    # e.g. "vstavridis/warehouse"
WAREHOUSE_GITHUB_BRANCH  # optional, defaults to "main"
```

(`QUEUE_GITHUB_TOKEN`/`QUEUE_GITHUB_REPO`/`QUEUE_GITHUB_BRANCH` and
`DISPLAY_GITHUB_TOKEN`/`DISPLAY_GITHUB_REPO`/`DISPLAY_GITHUB_BRANCH` are
also checked as fallbacks, matching Slitter's own secret names.)

⚠️ The restore/backup HTTP mechanics were verified in this dev sandbox
against the public, unauthenticated GitHub API (reachable here) with a
mocked token/response for the authenticated write path - a real token
against the actual repo needs to be verified once deployed.

### Database

SQLite is used for zero-setup local development, created and seeded
automatically on first run. All SQL lives in `backend/database.py`; every
other module goes through `backend/models.py`, `backend/tag_manager.py`,
or `backend/simulation.py`. To migrate to PostgreSQL later, only
`backend/database.py` needs to change (swap the `sqlite3` connection/
schema for `psycopg2`/SQLAlchemy) — no page or other backend module
touches SQL directly.

**Where the `.db` file actually lives** matters on hosts with an ephemeral
filesystem (Streamlit Community Cloud wipes the app's own directory on
redeploy/reboot) - that would silently reset every coil, tag, movement
record, and the stored OneDrive connection. `config._resolve_persistent_root()`
prefers, in order: a `WAREHOUSE_DATA_DIR` secret or env var, then
`/mount/data/warehouse_persistent`, then `/data/warehouse_persistent`,
then a dotfolder under the user's home directory, falling back to the
app's own `data/` folder only if none of those are writable. This
mirrors the same approach this warehouse's existing "Slitter" Streamlit
app already uses for its own persistent storage (its own equivalent
candidate list, e.g. `/mount/data/slitting_persistent`), so both apps
behave consistently on the same host. If an old database is found at the
app's own `data/warehouse.db` (e.g. from before this existed, or a host
without a persistent mount) and the resolved persistent location is
still empty, it's copied over automatically on the next startup rather
than starting fresh.

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
