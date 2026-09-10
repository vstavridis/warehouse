"""Simulation Control - manually trigger simulated coil movements."""

import streamlit as st

import config
from backend.database import init_db
from backend import models, simulation
from backend.ui import apply_page_chrome, render_nav

st.set_page_config(page_title="Simulation Control", page_icon="🎮", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/2_Simulation_Control.py")

st.title("🎮 Simulation Control")
st.caption("No real BLE hardware yet — trigger movements manually to test the tracking UX.")

coils = models.get_all_coils()
coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []
empty_positions = sorted(models.get_empty_positions())
all_positions = sorted(models.get_all_positions()["position_id"].tolist())

st.subheader("Manual movement")

c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
with c1:
    sel_coil = st.selectbox("Select Coil", options=coil_ids, key="manual_coil")
with c2:
    current = models.get_coil(sel_coil)["current_position"] if sel_coil else None
    st.text_input("Move From", value=current or "—", disabled=True)
with c3:
    dest_options = [p for p in all_positions if p != current]
    sel_dest = st.selectbox("Move To", options=dest_options, key="manual_dest")
with c4:
    st.write("")
    st.write("")
    start = st.button("🚀 Start Movement", type="primary", width="stretch")

if start and sel_coil and sel_dest:
    with st.spinner(f"Simulating movement of {sel_coil} to {sel_dest}..."):
        try:
            result = simulation.move_coil(sel_coil, sel_dest)
            st.success(
                f"{sel_coil} moved {result['from'] or '—'} → {result['to']} "
                f"(confidence {result['confidence']}%)"
            )
        except simulation.SimulationError as e:
            st.error(str(e))
    st.rerun()

st.divider()
st.subheader("Quick simulation buttons")

qcols = st.columns(3)


def quick_move(coil_id, to_position, container):
    with container:
        coil = models.get_coil(coil_id)
        label = f"Move {coil_id} {coil['current_position'] if coil else '?'} → {to_position}"
        if st.button(label, width="stretch", key=f"qm_{coil_id}_{to_position}"):
            try:
                simulation.move_coil(coil_id, to_position, animate=False)
                st.success(f"{coil_id} moved to {to_position}")
            except simulation.SimulationError as e:
                st.error(str(e))
            st.rerun()


quick_targets = [
    ("C0001", "A5"),
    ("C0002", "D8"),
    ("C0003", "A10"),
    ("C0004", "D6_7_UPPER"),
]
for i, (coil_id, target) in enumerate(quick_targets):
    if models.get_coil(coil_id):
        quick_move(coil_id, target, qcols[i % 3])

with qcols[1]:
    if st.button("🎲 Move random coil", width="stretch"):
        result = simulation.move_random_coil(animate=False)
        if result:
            st.success(f"{result['coil_id']} moved {result['from'] or '—'} → {result['to']}")
        else:
            st.warning("No eligible coil/position found for a random move.")
        st.rerun()

with qcols[2]:
    if st.button("🔀 Simulate 5 random movements", width="stretch"):
        results = simulation.simulate_n_random_movements(5, animate=False)
        st.success(f"Simulated {len(results)} movement(s).")
        st.rerun()

st.divider()
st.subheader("Current occupancy snapshot")
active = models.get_active_coils()
if not active.empty:
    st.dataframe(
        active[["coil_id", "status", "current_position", "previous_position", "location_confidence"]],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No coils currently placed in the warehouse.")
