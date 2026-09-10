"""
Builds the Plotly figure for the Area 1 warehouse map.

Occupied positions are rendered with a small metallic "coil" icon (a
top-down illustration of a rolled steel coil: concentric rings around a
dark core, with a specular highlight) instead of a plain shape, so the map
reads as an actual coil yard rather than an abstract grid. A colored halo
behind each icon encodes the coil's status, and the selected/searched coil
gets a distinct blue dashed halo.
"""

import base64
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
SELECTED_COLOR = "#1565C0"  # blue halo for selected/search coil

GROUND_ICON_SIZE = 1.05
UPPER_ICON_SIZE = 0.8


def _build_coil_icon_data_uri() -> str:
    """A small SVG illustration of a rolled steel coil viewed end-on:
    a metallic gradient disc, concentric wind lines, a dark core, and a
    diagonal specular highlight. Generated once and reused for every
    occupied position, since the halo behind it (not the icon itself)
    encodes status."""
    svg = """
    <svg width="200" height="200" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="metal" cx="35%" cy="32%" r="75%">
          <stop offset="0%" stop-color="#CFD8DC"/>
          <stop offset="35%" stop-color="#90A4AE"/>
          <stop offset="70%" stop-color="#546E7A"/>
          <stop offset="100%" stop-color="#263238"/>
        </radialGradient>
        <linearGradient id="shine" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.6"/>
          <stop offset="25%" stop-color="#FFFFFF" stop-opacity="0.08"/>
          <stop offset="45%" stop-color="#FFFFFF" stop-opacity="0"/>
        </linearGradient>
        <radialGradient id="core" cx="40%" cy="35%" r="70%">
          <stop offset="0%" stop-color="#37474F"/>
          <stop offset="100%" stop-color="#0B0F11"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="47" fill="url(#metal)" stroke="#12171A" stroke-width="1.5"/>
      <circle cx="50" cy="50" r="40" fill="none" stroke="#1A2226" stroke-width="0.8" opacity="0.6"/>
      <circle cx="50" cy="50" r="34" fill="none" stroke="#1A2226" stroke-width="0.8" opacity="0.6"/>
      <circle cx="50" cy="50" r="28" fill="none" stroke="#1A2226" stroke-width="0.8" opacity="0.6"/>
      <circle cx="50" cy="50" r="22" fill="none" stroke="#1A2226" stroke-width="0.8" opacity="0.6"/>
      <circle cx="50" cy="50" r="15" fill="url(#core)" stroke="#050708" stroke-width="1.5"/>
      <circle cx="50" cy="50" r="47" fill="url(#shine)"/>
    </svg>
    """
    encoded = base64.b64encode(svg.strip().encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


COIL_ICON_URI = _build_coil_icon_data_uri()


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

    # --- Legend swatches for coil statuses (fixed, so the legend is stable
    #     even if a status has no coils right now) ---
    for status, color in STATUS_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=14, color=color, symbol="circle"),
            name=status.title(),
        ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(size=14, color="rgba(0,0,0,0)", symbol="circle",
                    line=dict(width=3, color=SELECTED_COLOR)),
        name="Selected",
    ))

    # --- Occupied ground / upper coils: colored status halo + coil icon ---
    if not coils.empty:
        merged = coils.merge(positions, left_on="current_position", right_on="position_id")

        for row in merged.itertuples():
            is_selected = row.coil_id == selected_coil_id
            halo_color = STATUS_COLORS.get(row.status, "#455A64")
            icon_size = GROUND_ICON_SIZE if row.level == config.GROUND else UPPER_ICON_SIZE
            halo_radius = icon_size * 0.62

            fig.add_shape(
                type="circle", xref="x", yref="y",
                x0=row.x - halo_radius, x1=row.x + halo_radius,
                y0=row.y - halo_radius, y1=row.y + halo_radius,
                fillcolor=halo_color, opacity=0.30,
                line=dict(color=halo_color, width=2),
            )
            if is_selected:
                sel_radius = halo_radius + 0.18
                fig.add_shape(
                    type="circle", xref="x", yref="y",
                    x0=row.x - sel_radius, x1=row.x + sel_radius,
                    y0=row.y - sel_radius, y1=row.y + sel_radius,
                    fillcolor="rgba(0,0,0,0)",
                    line=dict(color=SELECTED_COLOR, width=3, dash="dash"),
                )

            fig.add_layout_image(dict(
                source=COIL_ICON_URI,
                x=row.x, y=row.y,
                xref="x", yref="y",
                xanchor="center", yanchor="middle",
                sizex=icon_size, sizey=icon_size,
                sizing="contain",
                layer="above",
            ))

        label = merged["coil_id"] + merged["level"].apply(
            lambda lv: " (U)" if lv == config.UPPER else ""
        )
        fig.add_trace(go.Scatter(
            x=merged["x"], y=merged["y"],
            mode="markers+text",
            marker=dict(size=1, color="rgba(0,0,0,0)"),
            text=label,
            textposition="bottom center",
            textfont=dict(size=9, color="#102027"),
            showlegend=False,
            hovertext=[
                f"{r.coil_id} @ {r.current_position}<br>Status: {r.status}<br>"
                f"Confidence: {r.location_confidence}%"
                for r in merged.itertuples()
            ],
            hoverinfo="text",
        ))

    # --- Column / aisle labels ---
    for col, y in config.COLUMN_Y.items():
        fig.add_annotation(x=-1.5, y=y, text=f"<b>{col}</b>", showarrow=False,
                            font=dict(size=16, color="#37474F"))

    fig.update_layout(
        height=560,
        margin=dict(l=40, r=20, t=20, b=20),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="#FAFAFA",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(title="Length (m)", range=[-2.5, config.AREA_LENGTH_M + 1], zeroline=False,
                   showgrid=True, gridcolor="#ECEFF1"),
        yaxis=dict(title="Width (m)", range=[-1, config.AREA_WIDTH_M + 1], zeroline=False,
                   showgrid=True, gridcolor="#ECEFF1", scaleanchor="x", scaleratio=1),
    )
    return fig
