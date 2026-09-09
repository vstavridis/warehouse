"""Locate Coil - search for a coil and highlight it on the warehouse map."""

import streamlit as st

import config
from backend.database import init_db
from backend import models
from backend.warehouse_map import build_map_figure
from backend.positioning import is_low_confidence

st.set_page_config(page_title="Locate Coil", page_icon="🔍", layout="wide")
init_db()

st.title("🔍 Locate Coil")

coils = models.get_all_coils()
coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []

search = st.selectbox("Search Coil", options=["-"] + coil_ids, index=0)

if "located_coil" not in st.session_state:
    st.session_state.located_coil = None

if search != "-":
    coil = models.get_coil(search)

    if coil["current_position"] is None:
        st.warning(f"{search} is currently **{coil['status']}** and has no position in the warehouse "
                   f"(likely sent to production).")
    else:
        position = models.get_position(coil["current_position"])
        st.success(f"Coil **{search}** found.")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Area", config.AREA_1)
            st.metric("Column", position["column_name"])
        with c2:
            st.metric("Position", position["position_id"])
            st.metric("Level", position["level"])
        with c3:
            st.metric("Tag", coil["tag_id"] or "—")
            conf = coil["location_confidence"]
            st.metric("Confidence", f"{conf}%" if conf is not None else "—")

        if is_low_confidence(conf):
            st.warning("Low location confidence")

        if st.button("📍 Show on Map", type="primary"):
            st.session_state.located_coil = search

if st.session_state.located_coil:
    st.divider()
    st.subheader(f"Warehouse Map — highlighting {st.session_state.located_coil}")
    fig = build_map_figure(selected_coil_id=st.session_state.located_coil)
    st.plotly_chart(fig, use_container_width=True)
