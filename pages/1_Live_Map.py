"""Live Warehouse Map - Area 1 (includes coil search / locate)."""

from datetime import datetime

import streamlit as st

import config
from backend.database import init_db
from backend import models
from backend.warehouse_map import build_map_figure
from backend.positioning import is_low_confidence

st.set_page_config(page_title="Live Map", page_icon="🗺️", layout="wide")
init_db()

st.title("🗺️ Live Warehouse Map — Area 1")

if "selected_coil" not in st.session_state:
    st.session_state.selected_coil = None


@st.fragment(run_every=config.LIVE_MAP_REFRESH_SECONDS)
def live_map():
    coils = models.get_active_coils()

    top = st.columns([5, 1])
    with top[1]:
        if st.button("🔄 Refresh now", width="stretch"):
            st.rerun(scope="fragment")

    fig = build_map_figure(selected_coil_id=st.session_state.selected_coil)
    event = st.plotly_chart(
        fig,
        width="stretch",
        theme=None,
        key="live_map_chart",
        on_select="rerun",
        selection_mode=["points"],
    )

    st.caption(
        f"Each metallic disc is a coil (small = upper position). Click a coil, or use the "
        f"search box below, to select it — the colored halo shows status, a blue dashed halo "
        f"marks the selected coil. Auto-refreshes every {config.LIVE_MAP_REFRESH_SECONDS}s "
        f"· last updated {datetime.now():%H:%M:%S}."
    )
    st.caption(
        "ℹ️ If the map is expanded to your browser's native fullscreen, background updates "
        "from other users may not repaint until you exit fullscreen or press **Refresh now** "
        "above — this is a browser/embedding limitation, not a data issue. The map is sized "
        "large by default so fullscreen shouldn't usually be needed."
    )

    # --- Click-to-select on the map ---
    if event and event.get("selection", {}).get("points"):
        for pt in event["selection"]["points"]:
            coil_id = pt.get("customdata")
            if coil_id:
                st.session_state.selected_coil = coil_id
                break

    st.divider()
    st.subheader("🔍 Search / Select Coil")

    coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []
    chosen = st.selectbox(
        "Type a coil ID to locate it",
        options=["-"] + coil_ids,
        index=0 if not st.session_state.selected_coil else
        (coil_ids.index(st.session_state.selected_coil) + 1
         if st.session_state.selected_coil in coil_ids else 0),
    )
    st.session_state.selected_coil = None if chosen == "-" else chosen

    if st.session_state.selected_coil:
        coil = models.get_coil(st.session_state.selected_coil)
        position = models.get_position(coil["current_position"]) if coil["current_position"] else None

        st.markdown(f"### {coil['coil_id']}")

        if position is None:
            st.warning(f"{coil['coil_id']} is currently **{coil['status']}** and has no "
                       f"position in the warehouse (likely sent to production).")
        else:
            status_icon = {
                config.COIL_STATUS_STATIONARY: "🟢",
                config.COIL_STATUS_MOVING: "🟠",
                config.COIL_STATUS_PRODUCTION: "⚪",
                config.COIL_STATUS_MISSING: "🔴",
            }.get(coil["status"], "⚪")

            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.markdown(f"**Status:** {status_icon} {coil['status']}")
                st.write(f"**Tag ID:** {coil['tag_id'] or '—'}")
            with d2:
                st.write(f"**Material:** {coil['material']}")
                st.write(f"**Weight:** {coil['weight_kg']:,.0f} kg")
            with d3:
                st.write(f"**Area:** {config.AREA_1}")
                st.write(f"**Column:** {position['column_name']}")
                st.write(f"**Position:** {position['position_id']}")
                st.write(f"**Level:** {position['level']}")
            with d4:
                st.write(f"**Last Movement:** {coil['last_movement'] or '—'}")
                st.write(f"**Last Seen:** {coil['last_seen'] or '—'}")
                conf = coil["location_confidence"]
                if conf is not None:
                    st.write(f"**Location Confidence:** {conf}%")

            if is_low_confidence(coil["location_confidence"]):
                st.warning("Low location confidence")
    else:
        st.info("Click a coil on the map, or search above, to see its full details here.")


live_map()
