"""
Builds the Plotly figure for the Area 1 warehouse map.

Kept separate from the Streamlit pages so both "Live Warehouse Map" and
"Locate Coil" (which needs to highlight a single coil) can reuse the same
rendering logic.
"""

from typing import Optional
import plotly.graph_objects as go

import config
from backend import models

STATUS_COLORS = {
    config.COIL_STATUS_STATIONARY: "#2E7D32",   # green
    config.COIL_STATUS_MOVING: "#F9A825",       # amber
    config.COIL_STATUS_PRODUCTION: "#616161",   # grey
    config.COIL_STATUS_MISSING: "#C62828",      # red
}
EMPTY_COLOR = "#CFD8DC"
SELECTED_COLOR = "#1565C0"  # blue ring for selected/search coil


def build_map_figure(selected_coil_id: Optional[str] = None) -> go.Figure:
    positions = models.get_all_positions()
    coils = models.get_active_coils()

    coil_by_position = {}
    if not coils.empty:
        for _, row in coils.iterrows():
            coil_by_position[row["current_position"]] = row

    fig = go.Figure()

    ground = positions[positions["level"] == config.GROUND]
    upper = positions[positions["level"] == config.UPPER]

    # --- Empty ground slots (background layer) ---
    empty_ground = ground[~ground["position_id"].isin(coil_by_position.keys())]
    fig.add_trace(go.Scatter(
        x=empty_ground["x"], y=empty_ground["y"],
        mode="markers+text",
        marker=dict(size=26, color=EMPTY_COLOR, symbol="square", line=dict(width=1, color="#90A4AE")),
        text=empty_ground["position_id"],
        textposition="middle center",
        textfont=dict(size=8, color="#455A64"),
        name="Empty",
        hovertext=empty_ground["position_id"],
        hoverinfo="text",
    ))

    # --- Empty upper slots ---
    empty_upper = upper[~upper["position_id"].isin(coil_by_position.keys())]
    fig.add_trace(go.Scatter(
        x=empty_upper["x"], y=empty_upper["y"],
        mode="markers",
        marker=dict(size=14, color="white", symbol="diamond", line=dict(width=1, color="#B0BEC5")),
        name="Empty (Upper)",
        hovertext=empty_upper["position_id"],
        hoverinfo="text",
    ))

    # --- Occupied ground / upper coils, grouped by status ---
    if not coils.empty:
        merged = coils.merge(positions, left_on="current_position", right_on="position_id")
        for level, size, symbol in ((config.GROUND, 30, "square"), (config.UPPER, 20, "diamond")):
            subset = merged[merged["level"] == level]
            if subset.empty:
                continue
            for status in subset["status"].unique():
                s = subset[subset["status"] == status]
                is_selected = s["coil_id"] == selected_coil_id
                colors = [SELECTED_COLOR if sel else STATUS_COLORS.get(status, "#455A64")
                          for sel in is_selected]
                line_widths = [3 if sel else 1 for sel in is_selected]
                fig.add_trace(go.Scatter(
                    x=s["x"], y=s["y"],
                    mode="markers+text",
                    marker=dict(size=size, color=colors, symbol=symbol,
                                line=dict(width=line_widths, color="#0D47A1")),
                    text=s["coil_id"],
                    textposition="middle center",
                    textfont=dict(size=8, color="white"),
                    name=f"{status.title()} ({level.title()})",
                    customdata=s["coil_id"],
                    hovertext=[
                        f"{r.coil_id} @ {r.current_position}<br>Status: {r.status}<br>"
                        f"Confidence: {r.location_confidence}%"
                        for r in s.itertuples()
                    ],
                    hoverinfo="text",
                ))

    # --- Column / aisle labels ---
    for col, y in config.COLUMN_Y.items():
        fig.add_annotation(x=-1.5, y=y, text=f"<b>{col}</b>", showarrow=False,
                            font=dict(size=16, color="#37474F"))

    fig.update_layout(
        height=520,
        margin=dict(l=40, r=20, t=20, b=20),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="#FAFAFA",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(title="Length (m)", range=[-2.5, config.AREA_LENGTH_M + 1], zeroline=False,
                   showgrid=True, gridcolor="#ECEFF1"),
        yaxis=dict(title="Width (m)", range=[-1, config.AREA_WIDTH_M + 1], zeroline=False,
                   showgrid=True, gridcolor="#ECEFF1"),
    )
    return fig
