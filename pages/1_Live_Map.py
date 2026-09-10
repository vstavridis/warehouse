"""Live Warehouse Map - Area 1 (includes coil search / locate)."""

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
            "Each metallic disc is a coil (small = upper position). The colored halo "
            "behind it shows status; a blue dashed halo marks the searched/selected coil. "
            f"Auto-refreshes every {config.LIVE_MAP_REFRESH_SECONDS}s."
        )

    with col_detail:
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
                st.markdown(f"**Status:** {status_icon} {coil['status']}")

                st.write(f"**Tag ID:** {coil['tag_id'] or '—'}")
                st.write(f"**Material:** {coil['material']}")
                st.write(f"**Weight:** {coil['weight_kg']:,.0f} kg")
                st.write(f"**Width:** {coil['width_mm']:,.0f} mm")
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
        else:
            st.info("Search or select a coil above to see full details and highlight it on the map.")


live_map()
