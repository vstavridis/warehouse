"""
3D Plotly figure for the Optimize page's truck-loading view: an open-sided
flatbed/curtainsider frame (just a floor + wireframe cage, not solid walls,
so the load is visible from both sides) plus one box per loaded pallet
(or, for a stack of sheet pallets, one box per physical layer so the
stack actually looks like separate pallets). Mouse rotate/zoom/pan comes
for free from Plotly's own 3D scene - no extra code needed for that.
"""

import plotly.graph_objects as go

import config

PALLET_COLORS = {
    "coil": "#52606d",    # steel gray
    "strips": "#2563eb",  # blue
    "sheet": "#c0c6cc",   # light silver
}

_BOX_TRIANGLES = [
    (0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
    (0, 1, 5), (0, 5, 4), (3, 2, 6), (3, 6, 7),
    (0, 3, 7), (0, 7, 4), (1, 2, 6), (1, 6, 5),
]


def _box_mesh(x0, y0, z0, dx, dy, dz, color, opacity=1.0):
    """A solid axis-aligned box from (x0,y0,z0) to (x0+dx,y0+dy,z0+dz)."""
    xs = [x0, x0 + dx, x0 + dx, x0, x0, x0 + dx, x0 + dx, x0]
    ys = [y0, y0, y0 + dy, y0 + dy, y0, y0, y0 + dy, y0 + dy]
    zs = [z0, z0, z0, z0, z0 + dz, z0 + dz, z0 + dz, z0 + dz]
    i = [t[0] for t in _BOX_TRIANGLES]
    j = [t[1] for t in _BOX_TRIANGLES]
    k = [t[2] for t in _BOX_TRIANGLES]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k, color=color, opacity=opacity,
        flatshading=True, hoverinfo="skip", showlegend=False, lighting=dict(ambient=0.6, diffuse=0.7),
    )


def _truck_frame_traces():
    L, W, H = config.TRUCK_LENGTH_MM, config.TRUCK_WIDTH_MM, config.TRUCK_HEIGHT_MM
    traces = [_box_mesh(0, 0, -80, L, W, 80, "#3f3f3f")]

    corners = [
        (0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0),
        (0, 0, H), (L, 0, H), (L, W, H), (0, W, H),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs += [corners[a][0], corners[b][0], None]
        ys += [corners[a][1], corners[b][1], None]
        zs += [corners[a][2], corners[b][2], None]
    traces.append(go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(color="#2b2b2b", width=4), hoverinfo="skip", showlegend=False,
    ))
    return traces


def build_truck_figure(placements=None) -> go.Figure:
    placements = placements or []
    fig = go.Figure()

    for trace in _truck_frame_traces():
        fig.add_trace(trace)

    for p in placements:
        color = PALLET_COLORS.get(p.kind, "#999999")

        if p.members and len(p.members) > 1:
            layer_h = p.height_mm / len(p.members)
            for idx in range(len(p.members)):
                z0 = p.z_mm + idx * layer_h
                fig.add_trace(_box_mesh(p.x_mm, p.y_mm, z0, p.length_mm, p.width_mm, layer_h * 0.92, color))
        else:
            fig.add_trace(_box_mesh(p.x_mm, p.y_mm, p.z_mm, p.length_mm, p.width_mm, p.height_mm, color))

        cx = p.x_mm + p.length_mm / 2
        cy = p.y_mm + p.width_mm / 2
        cz_top = p.z_mm + p.height_mm

        fig.add_trace(go.Scatter3d(
            x=[cx], y=[cy], z=[p.z_mm + p.height_mm / 2],
            mode="markers", marker=dict(size=1, opacity=0),
            hovertext=[f"{p.label}<br>{p.weight_kg:.0f} kg"], hoverinfo="text", showlegend=False,
        ))
        fig.add_trace(go.Scatter3d(
            x=[cx], y=[cy], z=[cz_top + 30],
            mode="text", text=[f"{p.weight_kg:.0f} kg"],
            textfont=dict(color="black", size=12, family="Arial Black"),
            showlegend=False, hoverinfo="skip",
        ))

    L, W, H = config.TRUCK_LENGTH_MM, config.TRUCK_WIDTH_MM, config.TRUCK_HEIGHT_MM
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Length (mm)", range=[-800, L + 800]),
            yaxis=dict(title="Width (mm)", range=[-800, W + 800]),
            zaxis=dict(title="Height (mm)", range=[-300, H + 1200]),
            aspectmode="data",
            camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=650,
        showlegend=False,
    )
    return fig
