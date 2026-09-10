"""
Builds the Plotly figure for the Area 1 warehouse map.

The map is styled to read like an actual warehouse floor plan (dark
building shell, light concrete floor, shaded storage lanes, aisle
markings) rather than an abstract scatter chart. Occupied positions are
rendered with a small metallic "coil" icon (a photo-inspired illustration
of a rolled steel coil: layered wind lines around a dark bore, a cast
shadow, and a specular highlight) instead of a plain shape. Only the
non-normal statuses (moving/missing) get a colored ring baked into the
icon - a plain stationary coil stays neutral metal so the floor isn't
awash in color. The selected/searched coil instead gets a bright green
ring, overriding any status ring. Every occupied position also carries
`customdata` on its hit-test trace so the page can drive click-to-select.
There is no legend and no axis scale drawn on the chart itself - both are
explained in a caption outside the figure instead.
"""

import base64
from typing import Optional

import plotly.graph_objects as go

import config
from backend import models

# Colors baked into the coil icon's outer ring. Stationary (the default,
# common state) intentionally gets the same neutral tone as the icon's own
# edge stroke, so normal coils don't read as having a colored background.
STATUS_RING_COLORS = {
    config.COIL_STATUS_STATIONARY: "#37474F",
    config.COIL_STATUS_MOVING: "#FB8C00",
    config.COIL_STATUS_PRODUCTION: "#9E9E9E",
    config.COIL_STATUS_MISSING: "#E53935",
}
SELECTED_RING_COLOR = "#00E676"  # bright green ring for the selected/searched coil

EMPTY_COLOR = "#9AA5AD"
EMPTY_BORDER = "#5C6B73"

FLOOR_COLOR = "#C9C4B7"
LANE_COLOR = "#B8B2A2"
BUILDING_BG = "#1B2126"
WALL_COLOR = "#0D1418"
AISLE_MARK_COLOR = "#E8B93A"

GROUND_ICON_SIZE = 1.05
UPPER_ICON_SIZE = 0.8


def _build_coil_icon_data_uri(ring_color: str, ring_width: float = 4.5) -> str:
    """A small SVG illustration of a rolled steel coil viewed end-on:
    a layered metallic gradient disc, tightly wound ring lines, a dark
    bore, and a bright diagonal specular highlight - styled after typical
    steel-coil warehouse photography, with a colored ring baked into the
    outer edge (rather than a translucent shape layered separately, since
    Plotly's shape/image stacking order is unreliable and a separate halo
    can end up tinting the whole icon)."""
    svg = f"""
    <svg width="220" height="220" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="metal" cx="34%" cy="30%" r="78%">
          <stop offset="0%" stop-color="#ECEFF1"/>
          <stop offset="22%" stop-color="#B0BEC5"/>
          <stop offset="48%" stop-color="#78909C"/>
          <stop offset="75%" stop-color="#455A64"/>
          <stop offset="100%" stop-color="#1A2327"/>
        </radialGradient>
        <linearGradient id="shine" x1="10%" y1="0%" x2="90%" y2="100%">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.75"/>
          <stop offset="18%" stop-color="#FFFFFF" stop-opacity="0.15"/>
          <stop offset="38%" stop-color="#FFFFFF" stop-opacity="0"/>
        </linearGradient>
        <radialGradient id="core" cx="38%" cy="32%" r="75%">
          <stop offset="0%" stop-color="#2E3A40"/>
          <stop offset="60%" stop-color="#12181B"/>
          <stop offset="100%" stop-color="#030506"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="none" stroke="{ring_color}" stroke-width="{ring_width}"/>
      <circle cx="50" cy="50" r="44" fill="url(#metal)" stroke="#0A0F11" stroke-width="1.5"/>
      <circle cx="50" cy="50" r="40" fill="none" stroke="#0F1518" stroke-width="0.6" opacity="0.55"/>
      <circle cx="50" cy="50" r="36.5" fill="none" stroke="#0F1518" stroke-width="0.9" opacity="0.7"/>
      <circle cx="50" cy="50" r="33" fill="none" stroke="#0F1518" stroke-width="0.6" opacity="0.55"/>
      <circle cx="50" cy="50" r="29.5" fill="none" stroke="#0F1518" stroke-width="0.9" opacity="0.7"/>
      <circle cx="50" cy="50" r="26" fill="none" stroke="#0F1518" stroke-width="0.6" opacity="0.55"/>
      <circle cx="50" cy="50" r="22.5" fill="none" stroke="#0F1518" stroke-width="0.9" opacity="0.7"/>
      <circle cx="50" cy="50" r="19" fill="none" stroke="#0F1518" stroke-width="0.6" opacity="0.55"/>
      <circle cx="50" cy="50" r="14" fill="url(#core)" stroke="#020304" stroke-width="1.6"/>
      <circle cx="50" cy="50" r="44" fill="url(#shine)"/>
      <path d="M 22 30 A 36 36 0 0 1 72 21" stroke="#FFFFFF" stroke-opacity="0.35"
            stroke-width="2.5" fill="none" stroke-linecap="round"/>
    </svg>
    """
    encoded = base64.b64encode(svg.strip().encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


COIL_ICON_URIS = {
    status: _build_coil_icon_data_uri(color) for status, color in STATUS_RING_COLORS.items()
}
SELECTED_ICON_URI = _build_coil_icon_data_uri(SELECTED_RING_COLOR, ring_width=7)


def _add_floor(fig: go.Figure) -> None:
    """Building shell, concrete floor, shaded storage lanes and painted
    aisle markings, so the chart reads like a real warehouse floor plan."""
    # Building shell (outer wall)
    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=-0.9, x1=config.AREA_LENGTH_M + 0.9,
        y0=-0.9, y1=config.AREA_WIDTH_M - 0.1,
        fillcolor=FLOOR_COLOR, line=dict(color=WALL_COLOR, width=4),
        layer="below",
    )

    # Shaded storage lane per column (ground + upper band)
    lane_half = 1.15
    for i, (col, y) in enumerate(config.COLUMN_Y.items()):
        if i % 2 == 0:
            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=-0.6, x1=config.AREA_LENGTH_M + 0.6,
                y0=y - lane_half, y1=y + lane_half,
                fillcolor=LANE_COLOR, opacity=0.55, line=dict(width=0),
                layer="below",
            )

    # Painted aisle centerline between each pair of neighboring columns
    col_ys = list(config.COLUMN_Y.values())
    for y_a, y_b in zip(col_ys, col_ys[1:]):
        mid = (y_a + y_b) / 2
        fig.add_shape(
            type="line", xref="x", yref="y",
            x0=-0.6, x1=config.AREA_LENGTH_M + 0.6, y0=mid, y1=mid,
            line=dict(color=AISLE_MARK_COLOR, width=2, dash="dash"),
            opacity=0.8, layer="below",
        )
        fig.add_annotation(
            x=config.AREA_LENGTH_M + 1.3, y=mid, text="AISLE", showarrow=False,
            font=dict(size=9, color="#6B655A"), textangle=-90,
        )


def build_map_figure(selected_coil_id: Optional[str] = None) -> go.Figure:
    positions = models.get_all_positions()
    coils = models.get_active_coils()

    coil_by_position = {}
    if not coils.empty:
        for _, row in coils.iterrows():
            coil_by_position[row["current_position"]] = row

    fig = go.Figure()
    _add_floor(fig)

    ground = positions[positions["level"] == config.GROUND]
    upper = positions[positions["level"] == config.UPPER]

    # --- Empty ground slots (background layer) ---
    empty_ground = ground[~ground["position_id"].isin(coil_by_position.keys())]
    fig.add_trace(go.Scatter(
        x=empty_ground["x"], y=empty_ground["y"],
        mode="markers+text",
        marker=dict(size=25, color=EMPTY_COLOR, symbol="square", line=dict(width=1, color=EMPTY_BORDER)),
        text=empty_ground["position_id"],
        textposition="middle center",
        textfont=dict(size=8, color="#20262B"),
        name="Empty",
        showlegend=False,
        hovertext=empty_ground["position_id"],
        hoverinfo="text",
    ))

    # --- Empty upper slots ---
    empty_upper = upper[~upper["position_id"].isin(coil_by_position.keys())]
    fig.add_trace(go.Scatter(
        x=empty_upper["x"], y=empty_upper["y"],
        mode="markers",
        marker=dict(size=13, color="#E4E1D6", symbol="diamond", line=dict(width=1, color=EMPTY_BORDER)),
        name="Empty (Upper)",
        showlegend=False,
        hovertext=empty_upper["position_id"],
        hoverinfo="text",
    ))

    # --- Occupied ground / upper coils: shadow + coil icon (status/selection ring baked in) ---
    if not coils.empty:
        merged = coils.merge(positions, left_on="current_position", right_on="position_id")

        for row in merged.itertuples():
            is_selected = row.coil_id == selected_coil_id
            icon_size = GROUND_ICON_SIZE if row.level == config.GROUND else UPPER_ICON_SIZE
            icon_radius = icon_size * 0.5

            # Cast shadow (subtle 3D grounding for the icon)
            shadow_dx, shadow_dy = icon_size * 0.07, -icon_size * 0.09
            shadow_r = icon_radius * 0.95
            fig.add_shape(
                type="circle", xref="x", yref="y",
                x0=row.x + shadow_dx - shadow_r, x1=row.x + shadow_dx + shadow_r,
                y0=row.y + shadow_dy - shadow_r, y1=row.y + shadow_dy + shadow_r,
                fillcolor="rgba(0,0,0,0.28)", line=dict(width=0),
            )

            icon_uri = SELECTED_ICON_URI if is_selected else COIL_ICON_URIS.get(
                row.status, COIL_ICON_URIS[config.COIL_STATUS_STATIONARY]
            )
            fig.add_layout_image(dict(
                source=icon_uri,
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
        icon_sizes = merged["level"].apply(
            lambda lv: GROUND_ICON_SIZE if lv == config.GROUND else UPPER_ICON_SIZE
        )
        # Marker sized to match the icon footprint (opacity 0) so the icon
        # is both hoverable and clickable for on-map coil selection.
        # `selectedpoints=[]` explicitly clears Plotly's own internal
        # selection memory on every single redraw - without it, Plotly.js
        # persists which point was last selected across re-renders
        # regardless of the component's key, so a second click on the
        # same coil gets read as a deselect (empty event) instead of a
        # new click, and the popup only reopens every other click.
        fig.add_trace(go.Scatter(
            x=merged["x"], y=merged["y"],
            mode="markers+text",
            marker=dict(size=[s * 42 for s in icon_sizes], color="rgba(0,0,0,0)"),
            text=label,
            textposition="bottom center",
            textfont=dict(size=9, color="#1A2126"),
            customdata=merged["coil_id"],
            selectedpoints=[],
            showlegend=False,
            hovertext=[
                f"{r.coil_id} @ {r.current_position}<br>Status: {r.status}<br>"
                f"Confidence: {r.location_confidence}%<br><i>Click to select</i>"
                for r in merged.itertuples()
            ],
            hoverinfo="text",
        ))

    # --- Column labels ---
    for col, y in config.COLUMN_Y.items():
        fig.add_annotation(x=-1.9, y=y, text=f"<b>{col}</b>", showarrow=False,
                            font=dict(size=18, color="#20262B"))

    fig.update_layout(
        height=config.LIVE_MAP_HEIGHT,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor=FLOOR_COLOR,
        paper_bgcolor=BUILDING_BG,
        showlegend=False,
        xaxis=dict(visible=False, range=[-2.6, config.AREA_LENGTH_M + 2.6]),
        yaxis=dict(visible=False, range=[-1.6, config.AREA_WIDTH_M + 1],
                   scaleanchor="x", scaleratio=1),
        clickmode="event+select",
    )

    # We render "selected" via a dedicated icon variant, so disable
    # Plotly's default behavior of dimming every other point once a
    # selection exists (it would otherwise wash out the whole floor plan).
    fig.update_traces(
        selected=dict(marker=dict(opacity=1)),
        unselected=dict(marker=dict(opacity=1)),
    )
    return fig
