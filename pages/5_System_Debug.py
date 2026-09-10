"""System Debug - inspect simulated RSSI readings per virtual receiver."""

import streamlit as st
import pandas as pd
import plotly.express as px

import config
from backend.database import init_db
from backend import models
from backend.positioning import simulate_rssi_for_position
from backend.ui import apply_page_chrome, render_nav

st.set_page_config(page_title="System Debug", page_icon="🛠️", layout="wide")
init_db()
apply_page_chrome()
render_nav(current="pages/5_System_Debug.py")

st.title("🛠️ System Debug — Simulated BLE Receivers")
st.caption(
    "This page is a placeholder for real hardware debugging. Today RSSI values are "
    "randomly simulated from each coil's known position; later this will show live "
    "readings streamed from the real ESP32 gateways over MQTT."
)

coils = models.get_active_coils()
coil_ids = sorted(coils["coil_id"].tolist()) if not coils.empty else []

if not coil_ids:
    st.info("No active coils to inspect.")
    st.stop()

selected = st.selectbox("Select coil", options=coil_ids)
coil = models.get_coil(selected)

if st.button("🔄 Refresh simulated RSSI"):
    st.rerun()

readings = simulate_rssi_for_position(coil["current_position"])
df = pd.DataFrame(
    [{"receiver": rx, "rssi_dbm": val} for rx, val in readings.items()]
).sort_values("rssi_dbm", ascending=False)

c1, c2 = st.columns([1, 2])
with c1:
    st.subheader(f"{selected} @ {coil['current_position']}")
    st.dataframe(df, width="stretch", hide_index=True)
    strongest = df.iloc[0]
    st.metric("Strongest signal", f"{strongest['receiver']}", f"{strongest['rssi_dbm']} dBm")

with c2:
    fig = px.bar(df, x="receiver", y="rssi_dbm", color="rssi_dbm",
                 color_continuous_scale="RdYlGn", range_color=[-100, -30])
    fig.update_layout(height=400, yaxis_title="RSSI (dBm)", xaxis_title="Receiver")
    st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Virtual receiver placement — Area 1")
rx_df = pd.DataFrame([
    {"receiver": rx, "x": data["x"], "y": data["y"]} for rx, data in config.RECEIVERS.items()
])
fig_layout = px.scatter(rx_df, x="x", y="y", text="receiver")
fig_layout.update_traces(marker=dict(size=16, color="#1565C0"), textposition="top center")
fig_layout.update_layout(
    height=350,
    xaxis=dict(title="Length (m)", range=[-1, config.AREA_LENGTH_M + 1]),
    yaxis=dict(title="Width (m)", range=[-1, config.AREA_WIDTH_M + 1]),
)
st.plotly_chart(fig_layout, width="stretch")

with st.expander("Future hardware message format"):
    st.code(
        '''{
  "gateway_id": "AREA1_RX03",
  "tag_id": "TAG-037",
  "rssi": -61,
  "timestamp": "2026-09-09T16:34:12"
}''',
        language="json",
    )
    st.caption(
        "backend/positioning.py::ingest_gateway_message() is the integration point where "
        "real MQTT/ESP32 messages like this will be consumed and fed into a real "
        "positioning algorithm."
    )
