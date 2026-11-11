"""Optimize - select ready-product pallets and load them into a truck."""

import io
from datetime import datetime

import streamlit as st

import config
from backend.database import init_db
from backend import models, onedrive, github_backup
from backend.ui import apply_page_chrome, render_nav
from backend.ready_products import import_ready_products_from_excel
from backend.truck_loading import pack_pallets
from backend.truck_figure import build_truck_figure

st.set_page_config(page_title="Optimize", page_icon="🚛", layout="wide")
init_db()
apply_page_chrome()
# render_nav disabled for AppTest debugging

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
        def _backup_settings_best_effort():
            # Best-effort: whenever this file's own settings change, back
            # them up to GitHub right away (if configured) too - the main
            # OneDrive connect flow already does this for the refresh
            # token itself, but these three settings can change later, on
            # this page, well after that initial connect.
            try:
                github_backup.backup_settings()
            except Exception:
                pass

        share_url_saved = models.get_setting(onedrive.SETTING_SHARE_URL_2, "") or ""
        share_url = st.text_input(
            "OneDrive link to the ready-products workbook",
            value=share_url_saved,
            placeholder="https://1drv.ms/x/...",
            key="ready_products_share_url",
        )
        if share_url != share_url_saved:
            models.set_setting(onedrive.SETTING_SHARE_URL_2, share_url)
            _backup_settings_best_effort()

        auto_saved = models.get_setting(onedrive.SETTING_AUTO_SYNC_ENABLED_2, "0") == "1"
        auto_enabled = st.checkbox("Automatically re-sync on a schedule", value=auto_saved, key="rp_auto_sync")
        if auto_enabled != auto_saved:
            models.set_setting(onedrive.SETTING_AUTO_SYNC_ENABLED_2, "1" if auto_enabled else "0")
            _backup_settings_best_effort()

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
            _backup_settings_best_effort()

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

st.divider()

# ---------------------------------------------------------------------------
# Selectable product table
# ---------------------------------------------------------------------------
products = models.get_all_ready_products()

if products.empty:
    st.warning("No ready-products data yet - connect/import the workbook above.")
    st.stop()

products = products.set_index("row_id")
text_cols = ["eidos", "paxos", "diastaseis", "pelatis", "barcode", "topothesia", "thesi"]
products[text_cols] = products[text_cols].fillna("")

DISPLAY_COLS = ["select", "eidos", "paxos", "diastaseis", "temaxia", "kila", "pelatis", "barcode", "topothesia", "thesi"]

FILTER_COLS = [
    ("pelatis", "ΠΕΛΑΤΗΣ"), ("diastaseis", "ΔΙΑΣΤΑΣΕΙΣ"), ("paxos", "ΠΑΧΟΣ"),
    ("eidos", "ΕΙΔΟΣ"), ("kila", "ΚΙΛΑ"),
]
FILTER_KEYS = {col: f"rp_filter_{col}" for col, _ in FILTER_COLS}

with st.expander("🔍 Filter", expanded=False):
    # Cascading: each filter's own dropdown only offers values that are
    # still reachable given what's currently chosen in the OTHER filters
    # (e.g. picking a ΠΕΛΑΤΗΣ narrows ΔΙΑΣΤΑΣΕΙΣ/ΠΑΧΟΣ/ΕΙΔΟΣ/ΚΙΛΑ to only
    # the combinations that customer actually has), rather than always
    # listing every value in the whole sheet regardless of other filters.
    current = {col: st.session_state.get(FILTER_KEYS[col], []) for col, _ in FILTER_COLS}
    chosen = {}
    widget_cols = st.columns(5)
    for (col, label), widget_col in zip(FILTER_COLS, widget_cols):
        subset = products
        for other_col, _ in FILTER_COLS:
            if other_col != col and current[other_col]:
                subset = subset[subset[other_col].isin(current[other_col])]
        options = sorted(subset[col].dropna().unique().tolist())

        key = FILTER_KEYS[col]
        pruned = [v for v in current[col] if v in options]
        if pruned != current[col]:
            st.session_state[key] = pruned

        with widget_col:
            if col == "kila":
                chosen[col] = st.multiselect(label, options, key=key, format_func=lambda v: f"{v:,.0f}")
            else:
                chosen[col] = st.multiselect(label, options, key=key)

filtered = products
for col, _ in FILTER_COLS:
    if chosen[col]:
        filtered = filtered[filtered[col].isin(chosen[col])]

# Selection is tracked independently of the current filter view (by
# row_id, in session_state) so narrowing/widening the filter never loses
# a selection made under a different filter - only the currently visible
# rows' checkboxes are reconciled back into it after each edit.
if "_rp_selected_ids" not in st.session_state:
    st.session_state["_rp_selected_ids"] = set()
selected_ids = st.session_state["_rp_selected_ids"]

editor_view = filtered.copy()
editor_view.insert(0, "select", editor_view.index.isin(selected_ids))

filter_key = "rp_filter_" + str(hash(tuple(tuple(chosen[col]) for col, _ in FILTER_COLS)))

edited = st.data_editor(
    editor_view[DISPLAY_COLS],
    hide_index=True,
    width="stretch",
    height=420,
    num_rows="fixed",
    key=filter_key,
    column_config={
        "select": st.column_config.CheckboxColumn("Select", default=False),
        "eidos": st.column_config.TextColumn("ΕΙΔΟΣ", disabled=True),
        "paxos": st.column_config.TextColumn("ΠΑΧΟΣ", disabled=True),
        "diastaseis": st.column_config.TextColumn("ΔΙΑΣΤΑΣΕΙΣ", disabled=True),
        "temaxia": st.column_config.NumberColumn("ΤΕΜΑΧΙΑ", disabled=True),
        "kila": st.column_config.NumberColumn("ΚΙΛΑ", disabled=True, format="%.0f"),
        "pelatis": st.column_config.TextColumn("ΠΕΛΑΤΗΣ", disabled=True),
        "barcode": st.column_config.TextColumn("BARCODE", disabled=True),
        "topothesia": st.column_config.TextColumn("ΤΟΠΟΘΕΣΙΑ", disabled=True),
        "thesi": st.column_config.TextColumn("ΘΕΣΗ", disabled=True),
    },
)

selected_ids = (selected_ids - set(editor_view.index)) | set(edited.index[edited["select"]])
st.session_state["_rp_selected_ids"] = selected_ids

selected = products.loc[products.index.isin(selected_ids)]
total_selected_kg = float(selected["kila"].fillna(0).sum()) if not selected.empty else 0.0
over_max = total_selected_kg > config.TRUCK_MAX_WEIGHT_KG

st.markdown(
    f"""
    <div style="position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); z-index: 9999;
                background: {'#b3261e' if over_max else '#1b5e20'}; color: #fff; padding: 10px 26px;
                border-radius: 999px; font-size: 1.05rem; font-weight: 600;
                box-shadow: 0 2px 12px rgba(0,0,0,0.3); white-space: nowrap;">
        {total_selected_kg:,.0f} / {config.TRUCK_MAX_WEIGHT_KG:,.0f} kg{' ⚠️ over max' if over_max else ''}
    </div>
    """,
    unsafe_allow_html=True,
)

if not selected.empty:
    st.caption(f"**{len(selected)} selected** — " + " · ".join(
        f"{row['diastaseis']} ({row['kila']:,.0f} kg)" for _, row in selected.iterrows()
    ))

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
