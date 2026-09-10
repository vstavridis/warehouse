"""Import Stock - load the real coil stock list from an exported Excel file."""

import streamlit as st

from backend.database import init_db
from backend.ui import apply_page_chrome, render_nav
from backend.stock_import import import_stock_from_excel

st.set_page_config(page_title="Import Stock", page_icon="📥", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/6_Import_Stock.py")

st.title("📥 Import Stock")
st.caption(
    "Upload the exported stock-list workbook (sheet **ΑΠΟΘΗΚΗ**) to replace the coils "
    "currently in the warehouse with the real stock list."
)

st.markdown(
    """
    Expected layout (row 1 = headers, last row = sums and is ignored):

    - **Column F** — unique coil id
    - **Column I** — map column: 1→A, 2→B, 3→C, 4→D, 5→E
    - **Column H** — position in the column (a single number for a ground
      position, e.g. `5` → `D5`; a pair like `4,5` for an upper position,
      e.g. → `B4_5_UPPER`)
    - **Column Q** — `Y` marks the coil as locked (shown with a 🔒 in its details)
    - **Columns A, B, C, D, E, G, K, P, R** — extra details shown in the
      coil popup, labeled with each column's own header text
    """
)

replace_existing = st.checkbox(
    "Replace all existing coils with this import", value=True,
    help="Unchecking this only adds/updates coils found in the file, without first clearing "
         "the warehouse - not usually what you want for a full stock refresh.",
)

uploaded = st.file_uploader("Stock list (.xlsx)", type=["xlsx"])

if uploaded is not None and st.button("Import", type="primary"):
    with st.spinner("Importing stock list..."):
        result = import_stock_from_excel(uploaded, replace_existing=replace_existing)

    if result.imported:
        st.success(f"Imported {result.imported} coil(s).")
    if result.skipped:
        st.warning(f"Skipped {result.skipped} row(s) — see details below.")
    if result.errors:
        with st.expander(f"Details ({len(result.errors)})", expanded=not result.imported):
            for e in result.errors:
                st.write(f"- {e}")
