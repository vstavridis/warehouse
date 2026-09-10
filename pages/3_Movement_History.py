"""Movement History - full audit trail of coil movements."""

import streamlit as st
import pandas as pd

from backend.database import init_db
from backend import models

st.set_page_config(page_title="Movement History", page_icon="📜", layout="wide")
init_db()

st.title("📜 Movement History")

history = models.get_movement_history()

if history.empty:
    st.info("No movements recorded yet.")
    st.stop()

history["timestamp"] = pd.to_datetime(history["timestamp"], format="mixed")
positions = models.get_all_positions()
pos_to_col = dict(zip(positions["position_id"], positions["column_name"]))
history["column"] = history["to_position"].map(pos_to_col).fillna(
    history["from_position"].map(pos_to_col)
)

st.subheader("Filters")
c1, c2, c3 = st.columns(3)
with c1:
    coil_filter = st.multiselect("Coil", options=sorted(history["coil_id"].unique()))
with c2:
    date_filter = st.date_input("Date", value=None)
with c3:
    column_filter = st.multiselect("Column", options=sorted(history["column"].dropna().unique()))

filtered = history.copy()
if coil_filter:
    filtered = filtered[filtered["coil_id"].isin(coil_filter)]
if date_filter:
    filtered = filtered[filtered["timestamp"].dt.date == date_filter]
if column_filter:
    filtered = filtered[filtered["column"].isin(column_filter)]

st.caption(f"{len(filtered)} movement(s)")
st.dataframe(
    filtered[[
        "timestamp", "coil_id", "tag_id", "from_position", "to_position",
        "movement_type", "confidence",
    ]].sort_values("timestamp", ascending=False),
    width="stretch",
    hide_index=True,
)
