"""Import Stock - load the real coil stock list, manually or from OneDrive."""

import io
from datetime import datetime

import streamlit as st

from backend import models, onedrive
from backend.database import init_db
from backend.ui import apply_page_chrome, render_nav
from backend.stock_import import import_stock_from_excel

st.set_page_config(page_title="Import Stock", page_icon="📥", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/6_Import_Stock.py")

st.title("📥 Import Stock")

st.markdown(
    """
    Columns are matched **by header text** (row 1), the same way the
    warehouse's existing stock-lookup tool reads this sheet — not by fixed
    column letters — so reordering or inserting columns won't break it.
    The last (sums) row is ignored, and if two coils resolve to the same
    position only the first one is kept (the rest are reported as skipped
    duplicates).

    - **Coil id** — header `Νο ΡΟΛΛΟΥ` (falls back to column F)
    - **Position** — header `ΘΕΣΗ` (falls back to column H): a single
      number is a ground position (`5` → `D5`); a pair like `4,5` is an
      upper position (→ `B4_5_UPPER`)
    - **Map column** — column I: `1`→A, `2`→B, `3`→C, `4`→D, `5`→E
      (no header-name equivalent exists in the other stock tool)
    - **Locked** — column Q, `Y` marks the coil as locked (shown with a
      red 🔒 in its details) (no header-name equivalent exists either)
    - **Details shown in the coil popup** — matched by header text if
      present: `ΕΙΔΟΣ`, `ΠΟΙΟΤΗΤΑ`, `ΠΑΧΟΣ`, `ΔΙΑΣΤΑΣΕΙΣ`/`ΠΛΑΤΟΣ`,
      `ΒΑΡΟΣ`, `ΜΕΤΡΑ`, `ΠΡΟΕΛΕΥΣΗ`, `ΤΟΜΕΑΣ`, `ΚΑΤΗΓΟΡΙΑ`, `ΤΙΜΗ`/`PRICE`,
      `ΠΕΡΙΓΡΑΦΗ`/`Description` — each shown labeled with whichever of
      those header spellings is actually found; missing ones are skipped
    """
)


def _show_import_result(result):
    if result.imported:
        st.success(f"Imported {result.imported} coil(s).")
    if result.skipped:
        st.warning(f"Skipped {result.skipped} row(s) — see details below.")
    if not result.imported and not result.skipped and result.errors:
        st.error(result.errors[0])

    if result.matched_columns:
        with st.expander("Which sheet columns were matched", expanded=not result.imported):
            st.caption(
                "Check this against your actual file — a field showing `None` means no "
                "matching header was found and that field was skipped entirely."
            )
            for label, col in result.matched_columns.items():
                st.write(f"- **{label}** → `{col}`")

    if result.errors:
        with st.expander(f"Row issues ({len(result.errors)})", expanded=False):
            for e in result.errors:
                st.write(f"- {e}")


st.divider()
st.subheader("🔗 Automatic sync from OneDrive")
st.caption(
    "Connect once and the app will keep re-pulling the workbook from OneDrive on its own — "
    "no more manual re-uploading. Uses the same Microsoft sign-in your Slitter tool already "
    "uses for this file."
)

connected = onedrive.is_connected()

if not connected:
    if st.button("🔑 Connect with Microsoft", type="primary"):
        try:
            st.session_state["_od_flow"] = onedrive.start_device_flow()
        except Exception as e:
            st.error(f"Could not start sign-in: {e}")

    flow = st.session_state.get("_od_flow")
    if flow:
        st.info(
            flow.get("message")
            or f"Go to **{flow['verification_uri']}** and enter code **{flow['user_code']}**"
        )
        if st.button("I've signed in — finish connecting"):
            with st.spinner("Waiting for Microsoft sign-in to complete..."):
                try:
                    token_response = onedrive.poll_device_flow(
                        flow["device_code"], flow.get("interval", 5), flow.get("expires_in", 900),
                    )
                    onedrive.complete_device_flow(token_response)
                except onedrive.OneDriveError as e:
                    st.error(str(e))
                else:
                    st.session_state.pop("_od_flow", None)
                    st.success("Connected to OneDrive.")
                    st.rerun()
else:
    c1, c2 = st.columns([4, 1])
    with c1:
        st.success("✅ Connected to OneDrive")
    with c2:
        if st.button("Disconnect", width="stretch"):
            onedrive.disconnect()
            st.rerun()

share_url_saved = models.get_setting(onedrive.SETTING_SHARE_URL, "") or ""
share_url = st.text_input(
    "OneDrive link to the stock workbook",
    value=share_url_saved,
    placeholder="https://onedrive.live.com/personal/.../doc.aspx?resid=...",
)
if share_url != share_url_saved:
    models.set_setting(onedrive.SETTING_SHARE_URL, share_url)

auto_enabled_saved = models.get_setting(onedrive.SETTING_AUTO_SYNC_ENABLED, "0") == "1"
auto_enabled = st.checkbox("Automatically re-sync on a schedule", value=auto_enabled_saved)
if auto_enabled != auto_enabled_saved:
    models.set_setting(onedrive.SETTING_AUTO_SYNC_ENABLED, "1" if auto_enabled else "0")

interval_saved = models.get_setting(onedrive.SETTING_SYNC_INTERVAL_SECONDS)
try:
    interval_minutes_saved = max(int(interval_saved), 30) // 60 if interval_saved else 5
except (TypeError, ValueError):
    interval_minutes_saved = 5
interval_minutes = st.number_input(
    "Sync interval (minutes)", min_value=1, max_value=180, value=max(interval_minutes_saved, 1),
    help="How often the app checks OneDrive for a newer file, whenever anyone has a page open.",
)
if interval_minutes * 60 != int(interval_saved or 0):
    models.set_setting(onedrive.SETTING_SYNC_INTERVAL_SECONDS, str(int(interval_minutes * 60)))

b1, b2 = st.columns(2)
with b1:
    if st.button("Verify connection", width="stretch", disabled=not (connected and share_url)):
        with st.spinner("Checking OneDrive..."):
            try:
                st.success(onedrive.verify_setup(share_url))
            except onedrive.OneDriveError as e:
                st.error(str(e))
with b2:
    if st.button("Sync now", type="primary", width="stretch", disabled=not (connected and share_url)):
        with st.spinner("Fetching the latest workbook from OneDrive..."):
            try:
                content, etag = onedrive.fetch_latest_stock_bytes(share_url)
            except onedrive.OneDriveError as e:
                st.error(str(e))
                models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, str(e))
            else:
                result = import_stock_from_excel(io.BytesIO(content), replace_existing=True)
                models.set_setting(onedrive.SETTING_LAST_SYNC_ETAG, etag or "")
                models.set_setting(onedrive.SETTING_LAST_SYNC_ERROR, "")
                _show_import_result(result)
        models.set_setting(onedrive.SETTING_LAST_SYNC_AT, datetime.now().isoformat(timespec="seconds"))

last_sync = models.get_setting(onedrive.SETTING_LAST_SYNC_AT)
last_error = models.get_setting(onedrive.SETTING_LAST_SYNC_ERROR)
if last_sync:
    if last_error:
        st.caption(f"Last sync attempt: {last_sync} — ⚠️ {last_error}")
    else:
        st.caption(f"Last sync attempt: {last_sync} — OK")

st.divider()
st.subheader("📤 Manual upload")
st.caption("For a one-off import, or if OneDrive sync isn't set up.")

replace_existing = st.checkbox(
    "Replace all existing coils with this import", value=True,
    help="Unchecking this only adds/updates coils found in the file, without first clearing "
         "the warehouse - not usually what you want for a full stock refresh.",
)

uploaded = st.file_uploader("Stock list (.xlsx)", type=["xlsx"])

if uploaded is not None and st.button("Import", type="primary"):
    with st.spinner("Importing stock list..."):
        result = import_stock_from_excel(uploaded, replace_existing=replace_existing)
    _show_import_result(result)
