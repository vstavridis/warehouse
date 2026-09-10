"""Live Warehouse Map - Area 1 (includes coil search / locate)."""

import streamlit as st

import config
from backend.database import init_db
from backend import models
from backend.ui import apply_page_chrome
from backend.warehouse_map import build_map_figure
from backend.positioning import is_low_confidence

st.set_page_config(page_title="Live Map", page_icon="🗺️", layout="wide")
init_db()
apply_page_chrome()

if "selected_coil" not in st.session_state:
    st.session_state.selected_coil = None
if "popup_shown_for" not in st.session_state:
    st.session_state.popup_shown_for = None


@st.dialog("Coil Details")
def show_coil_dialog(coil_id: str):
    coil = models.get_coil(coil_id)
    if coil is None:
        st.error(f"{coil_id} not found.")
        return

    position = models.get_position(coil["current_position"]) if coil["current_position"] else None

    st.markdown(f"### {coil['coil_id']}")

    if position is None:
        st.warning(f"{coil['coil_id']} is currently **{coil['status']}** and has no "
                   f"position in the warehouse (likely sent to production).")
        return

    status_icon = {
        config.COIL_STATUS_STATIONARY: "🟢",
        config.COIL_STATUS_MOVING: "🟠",
        config.COIL_STATUS_PRODUCTION: "⚪",
        config.COIL_STATUS_MISSING: "🔴",
    }.get(coil["status"], "⚪")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Status:** {status_icon} {coil['status']}")
        st.write(f"**Tag ID:** {coil['tag_id'] or '—'}")
        st.write(f"**Material:** {coil['material']}")
        st.write(f"**Weight:** {coil['weight_kg']:,.0f} kg")
    with c2:
        st.write(f"**Area:** {config.AREA_1}")
        st.write(f"**Column:** {position['column_name']}")
        st.write(f"**Position:** {position['position_id']}")
        st.write(f"**Level:** {position['level']}")

    st.write(f"**Last Movement:** {coil['last_movement'] or '—'}")
    st.write(f"**Last Seen:** {coil['last_seen'] or '—'}")

    conf = coil["location_confidence"]
    if conf is not None:
        st.write(f"**Location Confidence:** {conf}%")
        if is_low_confidence(conf):
            st.warning("Low location confidence")


top = st.columns([6, 1])
with top[0]:
    st.title("🗺️ Live Warehouse Map — Area 1")
with top[1]:
    st.page_link("app.py", label="🏠 Home", width="stretch")


@st.fragment(run_every=config.LIVE_MAP_REFRESH_SECONDS)
def live_map():
    coils = models.get_active_coils()
    coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []

    chosen = st.selectbox(
        "🔍 Search Coil",
        options=["-"] + coil_ids,
        index=0 if not st.session_state.selected_coil else
        (coil_ids.index(st.session_state.selected_coil) + 1
         if st.session_state.selected_coil in coil_ids else 0),
    )
    st.session_state.selected_coil = None if chosen == "-" else chosen

    fig = build_map_figure(selected_coil_id=st.session_state.selected_coil)
    event = st.plotly_chart(
        fig,
        width="stretch",
        theme=None,
        key="live_map_chart",
        on_select="rerun",
        selection_mode=["points"],
    )

    if event and event.get("selection", {}).get("points"):
        for pt in event["selection"]["points"]:
            coil_id = pt.get("customdata")
            if coil_id:
                st.session_state.selected_coil = coil_id
                break

    # Open the details popup only when the selection actually changed, so
    # it doesn't keep re-opening itself on every auto-refresh tick or
    # after the viewer closes it.
    if (st.session_state.selected_coil
            and st.session_state.popup_shown_for != st.session_state.selected_coil):
        st.session_state.popup_shown_for = st.session_state.selected_coil
        show_coil_dialog(st.session_state.selected_coil)

    st.divider()
    nav = st.columns(4)
    with nav[0]:
        st.page_link("pages/2_Simulation_Control.py", label="🎮 Simulation", width="stretch")
    with nav[1]:
        st.page_link("pages/3_Movement_History.py", label="📜 Movement", width="stretch")
    with nav[2]:
        st.page_link("pages/4_Tag_Management.py", label="🏷️ Management", width="stretch")
    with nav[3]:
        st.page_link("pages/5_System_Debug.py", label="🛠️ Debug", width="stretch")


live_map()
