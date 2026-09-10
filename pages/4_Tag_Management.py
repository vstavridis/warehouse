"""Tag Management - assign/release BLE tags, create coils, send to production."""

import streamlit as st

import config
from backend.database import init_db
from backend import models, tag_manager
from backend.ui import apply_page_chrome, render_nav

st.set_page_config(page_title="Tag Management", page_icon="🏷️", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/4_Tag_Management.py")

st.title("🏷️ Tag Management")

tags = models.get_all_tags()

st.subheader("Tag pool")
if not tags.empty:
    display = tags.copy()
    display["coil_id"] = display["coil_id"].fillna("-")
    st.dataframe(
        display[["tag_id", "coil_id", "status"]],
        width="stretch",
        hide_index=True,
    )

st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("Assign tag to coil")
    available_tags = models.get_available_tags()
    coils = models.get_all_coils()
    assignable_coils = coils[coils["status"] != config.COIL_STATUS_PRODUCTION]["coil_id"].tolist() \
        if not coils.empty else []

    if available_tags and assignable_coils:
        tag_to_assign = st.selectbox("Available tag", options=available_tags)
        coil_to_tag = st.selectbox("Coil", options=assignable_coils)
        if st.button("Assign Tag", type="primary"):
            try:
                tag_manager.assign_tag(tag_to_assign, coil_to_tag)
                st.success(f"{tag_to_assign} assigned to {coil_to_tag}")
                st.rerun()
            except tag_manager.TagError as e:
                st.error(str(e))
    else:
        st.info("No available tags or eligible coils.")

with c2:
    st.subheader("Release tag")
    in_use_tags = tags[tags["status"] == config.TAG_STATUS_IN_USE]["tag_id"].tolist() \
        if not tags.empty else []
    if in_use_tags:
        tag_to_release = st.selectbox("In-use tag", options=in_use_tags)
        if st.button("Release Tag"):
            try:
                tag_manager.release_tag(tag_to_release)
                st.success(f"{tag_to_release} released and now available.")
                st.rerun()
            except tag_manager.TagError as e:
                st.error(str(e))
    else:
        st.info("No tags currently in use.")

st.divider()
c3, c4 = st.columns(2)

with c3:
    st.subheader("Create new coil")
    with st.form("create_coil_form"):
        new_id = models.get_next_coil_id()
        st.text_input("Coil ID (auto-generated)", value=new_id, disabled=True)
        material = st.selectbox("Material", options=config.MATERIALS)
        weight = st.number_input("Weight (kg)", min_value=float(config.WEIGHT_MIN_KG),
                                  max_value=float(config.WEIGHT_MAX_KG),
                                  value=float((config.WEIGHT_MIN_KG + config.WEIGHT_MAX_KG) / 2))
        width = st.number_input("Width (mm)", min_value=float(config.WIDTH_MIN_MM),
                                 max_value=float(config.WIDTH_MAX_MM),
                                 value=float((config.WIDTH_MIN_MM + config.WIDTH_MAX_MM) / 2))
        empty_positions = sorted(models.get_empty_positions())
        position = st.selectbox("Initial position", options=empty_positions)
        tag_options = ["(none)"] + models.get_available_tags()
        tag_choice = st.selectbox("Assign tag", options=tag_options)

        submitted = st.form_submit_button("Create New Coil", type="primary")
        if submitted:
            if not empty_positions:
                st.error("No empty positions available.")
            else:
                tag_id = None if tag_choice == "(none)" else tag_choice
                models.create_coil(new_id, material, weight, width, position, tag_id)
                if tag_id:
                    tag_manager.assign_tag(tag_id, new_id)
                st.success(f"Created {new_id} at {position}.")
                st.rerun()

with c4:
    st.subheader("Send coil to production")
    active_coils = models.get_active_coils()
    active_ids = active_coils["coil_id"].tolist() if not active_coils.empty else []
    if active_ids:
        coil_to_send = st.selectbox("Coil", options=active_ids, key="production_coil")
        if st.button("Send Coil To Production", type="secondary"):
            try:
                tag_manager.send_to_production(coil_to_send)
                st.success(f"{coil_to_send} sent to production. Its tag is now available for reuse.")
                st.rerun()
            except tag_manager.TagError as e:
                st.error(str(e))
    else:
        st.info("No active coils in the warehouse.")
