"""
Steel Coil Warehouse Tracking - Milestone 1 Software Simulation Prototype

Entry point. Initializes the SQLite database (creating + seeding demo data
on first run) and renders the landing dashboard with top-level KPIs. The
actual functional pages live under pages/ and appear in the Streamlit
sidebar automatically.
"""

import streamlit as st
import pandas as pd

import config
from backend.database import init_db
from backend import models

st.set_page_config(
    page_title="Steel Coil Warehouse Tracking",
    page_icon="🏭",
    layout="wide",
)

init_db()

st.markdown(
    """
    <style>
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
    }
    .kpi-value { font-size: 32px; font-weight: 700; color: #1565C0; }
    .kpi-label { font-size: 13px; color: #607D8B; text-transform: uppercase; letter-spacing: 0.5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏭 Steel Coil Warehouse Tracking System")
st.caption("Milestone 1 — Software Simulation Prototype (no BLE hardware yet, all inputs simulated)")

coils = models.get_all_coils()
tags = models.get_all_tags()
movements = models.get_movement_history()

total_coils = len(coils)
in_area1 = int((coils["current_position"].notna()).sum()) if not coils.empty else 0
moving = int((coils["status"] == config.COIL_STATUS_MOVING).sum()) if not coils.empty else 0
available_tags = int((tags["status"] == config.TAG_STATUS_AVAILABLE).sum()) if not tags.empty else 0

production_today = 0
if not movements.empty:
    movements["timestamp"] = pd.to_datetime(movements["timestamp"])
    today = pd.Timestamp.now().normalize()
    production_today = int((
        (movements["movement_type"] == config.MOVEMENT_TYPE_PRODUCTION) &
        (movements["timestamp"] >= today)
    ).sum())

cols = st.columns(5)
kpis = [
    ("Total Coils", total_coils),
    ("Coils in Area 1", in_area1),
    ("Moving", moving),
    ("Available Tags", available_tags),
    ("Production Today", production_today),
]
for col, (label, value) in zip(cols, kpis):
    with col:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-value">{value}</div>'
            f'<div class="kpi-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

st.divider()

st.subheader("Getting started")
st.markdown(
    """
    Use the sidebar to navigate:

    - **Live Warehouse Map** — see every coil in Area 1 in real time, and search/locate any coil directly from this page.
    - **Simulation Control** — manually trigger simulated coil movements.
    - **Movement History** — full audit trail of every recorded movement.
    - **Tag Management** — assign / release BLE tags and send coils to production.
    - **System Debug** — inspect simulated RSSI readings from the virtual receivers.
    """
)

with st.expander("Area 1 layout summary"):
    st.write(
        f"Dimensions: **{config.AREA_LENGTH_M} m x {config.AREA_WIDTH_M} m** &nbsp;|&nbsp; "
        f"Columns: **{', '.join(config.COLUMNS)}** &nbsp;|&nbsp; "
        f"Ground positions: **{len(config.COLUMNS) * config.SLOTS_PER_COLUMN}** &nbsp;|&nbsp; "
        f"Upper positions: **{len(config.COLUMNS) * (config.SLOTS_PER_COLUMN - 1)}**"
    )
