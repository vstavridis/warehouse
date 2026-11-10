"""Optimize - select ready-product pallets and load them into a truck."""

import io
from datetime import datetime

import streamlit as st

import config
from backend.database import init_db
from backend import models, onedrive
from backend.ui import apply_page_chrome, render_nav
from backend.ready_products import import_ready_products_from_excel
from backend.truck_loading import pack_pallets
from backend.truck_figure import build_truck_figure

st.set_page_config(page_title="Optimize", page_icon="🚛", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/7_Optimize.py")

st.title("🚛 Optimize")
st.caption(
    "Select finished-product pallets from the ΄Ετοιμα προϊόντα list below and "
    "load them into a truck for the best fit by weight and dimensions."
)

# ---------------------------------------------------------------------------
# Ready-products file source (second OneDrive file, same Microsoft account)
# ---------------------------------------------------------------------------
with st.expander("🔗 Ready-products file source (OneDrive / manual upload)"):
    if not onedrive.is_connected():
        st.info(
            "Not connected to OneDrive yet - connect on the **📥 Import Stock** page "
            "first (same Microsoft account works for both files), then come back here."
        )
    else:
        share_url_saved = models.get_setting(onedrive.SETTING_SHARE_URL_2, "") or ""
        share_url = st.text_input(
            "OneDrive link to the ready-products workbook",
            value=share_url_saved,
            placeholder="https://1drv.ms/x/...",
            key="ready_products_share_url",
        )
        if share_url != share_url_saved:
            models.set_setting(onedrive.SETTING_SHARE_URL_2, share_url)

        auto_saved = models.get_setting(onedrive.SETTING_AUTO_SYNC_ENABLED_2, "0") == "1"
        auto_enabled = st.checkbox("Automatically re-sync on a schedule", value=auto_saved, key="rp_auto_sync")
        if auto_enabled != auto_saved:
            models.set_setting(onedrive.SETTING_AUTO_SYNC_ENABLED_2, "1" if auto_enabled else "0")

        interval_saved = models.get_setting(onedrive.SETTING_SYNC_INTERVAL_SECONDS_2)
        try:
            interval_minutes_saved = max(int(interval_saved), 30) // 60 if interval_saved else 5
        except (TypeError, ValueError):
            interval_minutes_saved = 5
        interval_minutes = st.number_input(
            "Sync interval (minutes)", min_value=1, max_value=180,
            value=max(interval_minutes_saved, 1), key="rp_interval",
        )
        if interval_minutes * 60 != int(interval_saved or 0):
            models.set_setting(onedrive.SETTING_SYNC_INTERVAL_SECONDS_2, str(int(interval_minutes * 60)))

        if st.button("Sync now", type="primary", disabled=not share_url):
            with st.spinner("Fetching the latest ready-products workbook from OneDrive..."):
                try:
                    content, etag = onedrive.fetch_latest_stock_bytes(share_url)
                except onedrive.OneDriveError as e:
                    st.error(str(e))
                    models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR_2, str(e))
                else:
                    result = import_ready_products_from_excel(io.BytesIO(content))
                    models.set_setting(onedrive.SETTING_LAST_SYNC_ETAG_2, etag or "")
                    models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR_2, "")
                    if result.imported:
                        st.success(f"Imported {result.imported} row(s).")
                    if result.errors:
                        st.error(result.errors[0])
            models.set_setting(onedrive.SETTING_LAST_SYNC_AT_2, datetime.now().isoformat(timespec="seconds"))
            st.rerun()

        last_sync_2 = models.get_setting(onedrive.SETTING_LAST_SYNC_AT_2)
        last_error_2 = models.get_setting(onedrive.SETTING_LAST_SYNC_ERROR_2)
        if last_sync_2:
            st.caption(f"Last sync attempt: {last_sync_2}" + (f" — ⚠️ {last_error_2}" if last_error_2 else " — OK"))

    st.divider()
    st.caption("Or upload the workbook manually (one-off import):")
    uploaded = st.file_uploader("Ready-products workbook (.xlsx)", type=["xlsx"], key="rp_manual_upload")
    if uploaded is not None and st.button("Import"):
        result = import_ready_products_from_excel(uploaded)
        if result.imported:
            st.success(f"Imported {result.imported} row(s).")
        if result.errors:
            st.error(result.errors[0])
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Selectable product table
# ---------------------------------------------------------------------------
products = models.get_all_ready_products()

if products.empty:
    st.warning("No ready-products data yet - connect/import the workbook above.")
    st.stop()

products = products.set_index("row_id")
text_cols = [
    "eidos", "paxos", "diastaseis", "pelatis", "vs_pg", "barcode",
    "topothesia", "thesi", "rolo", "poiotita", "xora", "ext_id", "imerominia",
]
products[text_cols] = products[text_cols].fillna("")
products.insert(0, "select", False)

edited = st.data_editor(
    products,
    hide_index=True,
    width="stretch",
    height=420,
    num_rows="fixed",
    key="ready_products_editor",
    column_config={
        "select": st.column_config.CheckboxColumn("Select", default=False),
        "eidos": st.column_config.TextColumn("ΕΙΔΟΣ", disabled=True),
        "paxos": st.column_config.TextColumn("ΠΑΧΟΣ", disabled=True),
        "diastaseis": st.column_config.TextColumn("ΔΙΑΣΤΑΣΕΙΣ", disabled=True),
        "temaxia": st.column_config.NumberColumn("ΤΕΜΑΧΙΑ", disabled=True),
        "kila": st.column_config.NumberColumn("ΚΙΛΑ", disabled=True, format="%.0f"),
        "pelatis": st.column_config.TextColumn("ΠΕΛΑΤΗΣ", disabled=True),
        "vs_pg": st.column_config.TextColumn("VS/PG", disabled=True),
        "barcode": st.column_config.TextColumn("BARCODE", disabled=True),
        "topothesia": st.column_config.TextColumn("ΤΟΠΟΘΕΣΙΑ", disabled=True),
        "thesi": st.column_config.TextColumn("ΘΕΣΗ", disabled=True),
        "rolo": st.column_config.TextColumn("ΡΟΛΟ", disabled=True),
        "poiotita": st.column_config.TextColumn("ΠΟΙΟΤΗΤΑ", disabled=True),
        "xora": st.column_config.TextColumn("ΧΩΡΑ", disabled=True),
        "ext_id": st.column_config.TextColumn("ID", disabled=True),
        "kostos": st.column_config.NumberColumn("ΚΟΣΤΟΣ", disabled=True),
        "imerominia": st.column_config.TextColumn("ΗΜΕΡΟΜΗΝΙΑ", disabled=True),
    },
)

selected = edited[edited["select"]]
total_selected_kg = float(selected["kila"].fillna(0).sum()) if not selected.empty else 0.0

st.metric("Selected weight (ΚΙΛΑ)", f"{total_selected_kg:,.0f} kg")

if not selected.empty:
    st.markdown("**Selected pallets**")
    for row_id, row in selected.iterrows():
        st.write(f"- **{row['diastaseis']}** — {row['kila']:,.0f} kg")

st.divider()

# ---------------------------------------------------------------------------
# Truck loading
# ---------------------------------------------------------------------------
st.subheader("Truck loading")
st.caption(
    f"Truck: {config.TRUCK_LENGTH_MM/1000:.2f} m x {config.TRUCK_WIDTH_MM/1000:.2f} m x "
    f"{config.TRUCK_HEIGHT_MM/1000:.2f} m — max {config.TRUCK_MAX_WEIGHT_KG/1000:.1f} t. "
    "Drag with the mouse to rotate/pan/zoom."
)

if st.button("⚙️ Optimize loading", type="primary", disabled=selected.empty):
    selected_rows = [
        {"row_id": row_id, "eidos": row["eidos"], "diastaseis": row["diastaseis"], "kila": row["kila"]}
        for row_id, row in selected.iterrows()
    ]
    st.session_state["_truck_packing_result"] = pack_pallets(selected_rows)

result = st.session_state.get("_truck_packing_result")

if result is not None:
    used_pct = result.total_weight_kg / config.TRUCK_MAX_WEIGHT_KG * 100
    length_pct = result.used_length_mm / config.TRUCK_LENGTH_MM * 100
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Loaded weight", f"{result.total_weight_kg:,.0f} / {config.TRUCK_MAX_WEIGHT_KG:,.0f} kg", f"{used_pct:.0f}%")
    with c2:
        st.metric("Length used", f"{result.used_length_mm/1000:.2f} / {config.TRUCK_LENGTH_MM/1000:.2f} m", f"{length_pct:.0f}%")
    if result.warnings:
        with st.expander(f"⚠️ {len(result.warnings)} item(s) need attention", expanded=False):
            for w in result.warnings:
                st.write(f"- {w}")
    st.plotly_chart(build_truck_figure(result.placements), width="stretch", theme=None)
else:
    st.plotly_chart(build_truck_figure(None), width="stretch", theme=None)
