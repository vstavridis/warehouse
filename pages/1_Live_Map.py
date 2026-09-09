"""Live Warehouse Map - Area 1"""

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

    col_map, col_detail = st.columns([3, 1])

    with col_map:
        fig = build_map_figure(selected_coil_id=st.session_state.selected_coil)
        st.plotly_chart(fig, use_container_width=True, key="live_map_chart")
        st.caption(
            "Square = ground position, Diamond = upper position. "
            "Blue outline marks the selected coil. Auto-refreshes every "
            f"{config.LIVE_MAP_REFRESH_SECONDS}s."
        )

    with col_detail:
        st.subheader("Select a coil")
        coil_ids = coils["coil_id"].tolist() if not coils.empty else []
        chosen = st.selectbox(
            "Active coils in Area 1",
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
            status_icon = {
                config.COIL_STATUS_STATIONARY: "🟢",
                config.COIL_STATUS_MOVING: "🟠",
                config.COIL_STATUS_PRODUCTION: "⚪",
                config.COIL_STATUS_MISSING: "🔴",
            }.get(coil["status"], "⚪")
            st.markdown(f"**Status:** {status_icon} {coil['status']}")

            st.write(f"**Tag ID:** {coil['tag_id'] or '—'}")
            st.write(f"**Material:** {coil['material']}")
            st.write(f"**Weight:** {coil['weight_kg']:,.0f} kg")
            st.write(f"**Width:** {coil['width_mm']:,.0f} mm")
            st.write(f"**Current Area:** {config.AREA_1 if position else '—'}")
            if position:
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
        else:
            st.info("Select a coil to see full details.")


live_map()
