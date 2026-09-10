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
    Columns are matched **by header text** (row 1), the same way the
    warehouse's existing stock-lookup tool reads this sheet — not by fixed
    column letters — so reordering or inserting columns won't break it.
    The last (sums) row is ignored.

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

    if result.matched_columns:
        with st.expander("Which sheet columns were matched", expanded=not result.imported):
            st.caption(
                "Check this against your actual file — a field showing `None` means no "
                "matching header was found and that field was skipped entirely."
            )
            for label, col in result.matched_columns.items():
                st.write(f"- **{label}** → `{col}`")

    if result.errors:
        with st.expander(f"Row issues ({len(result.errors)})", expanded=not result.imported):
            for e in result.errors:
                st.write(f"- {e}")
