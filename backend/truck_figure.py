"""
3D Plotly figure for the Optimize page's truck-loading view.

The trailer itself is an open-sided flatbed/curtainsider frame (just a
floor + wireframe cage, not solid walls, so the load is visible from
both sides), with a simple tractor cab + wheels in front of it so the
whole rendering reads as a real truck rather than a bare platform.
Mouse rotate/zoom/pan comes for free from Plotly's own 3D scene.

Pallets are drawn to roughly match this warehouse's own reference
photos rather than as plain boxes: a coil/strips pallet is a wood pallet
base topped by a real cylinder with a visible bore ("eye") - lying on
its side (axis along the truck's length) for a coil, standing upright
("eye to the sky") for strips - and a sheet pallet is a wood pallet base
topped by a flat stack of sheet layers.
"""

import numpy as np
import plotly.graph_objects as go

import config

PALLET_COLORS = {
    "coil": "#5b6670",
    "strips": "#3f6fb0",
    "sheet": "#c7ccd1",
}
WOOD_COLOR = "#c9975a"
BORE_COLOR = "#232629"
STRAP_COLOR = "#2b2f33"

PALLET_WOOD_HEIGHT_MM = 120

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


def _circle_points(center, axis, radius, n):
    """Points around a circle of `radius` centered at `center`, lying in
    the plane perpendicular to `axis` ('x', 'y', or 'z'). Always returns
    three same-length arrays (the constant coordinate is broadcast)."""
    theta = np.linspace(0, 2 * np.pi, n)
    cx, cy, cz = center
    ones = np.ones_like(theta)
    if axis == "x":
        return cx * ones, cy + radius * np.cos(theta), cz + radius * np.sin(theta)
    if axis == "z":
        return cx + radius * np.cos(theta), cy + radius * np.sin(theta), cz * ones
    return cx + radius * np.cos(theta), cy * ones, cz + radius * np.sin(theta)  # axis == "y"


def _disk_mesh(center, axis, radius, color, n=28, opacity=1.0):
    """A filled disk (triangle fan) - used for cylinder end caps."""
    xs, ys, zs = _circle_points(center, axis, radius, n)
    xs, ys, zs = [center[0]] + list(xs), [center[1]] + list(ys), [center[2]] + list(zs)
    i = [0] * (n - 1)
    j = list(range(1, n))
    k = list(range(2, n + 1))
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k, color=color, opacity=opacity,
        hoverinfo="skip", showlegend=False, flatshading=True,
    )


def _cylinder_tube(start_center, axis, radius, length, color, n=28, opacity=1.0):
    """The curved side surface of a cylinder running from start_center
    along `axis` for `length`, as a go.Surface."""
    theta = np.linspace(0, 2 * np.pi, n)
    t, theta_grid = np.meshgrid(np.array([0.0, 1.0]), theta, indexing="ij")
    cx, cy, cz = start_center
    if axis == "x":
        X = cx + t * length
        Y = cy + radius * np.cos(theta_grid)
        Z = cz + radius * np.sin(theta_grid)
    elif axis == "z":
        Z = cz + t * length
        X = cx + radius * np.cos(theta_grid)
        Y = cy + radius * np.sin(theta_grid)
    else:  # axis == "y"
        Y = cy + t * length
        X = cx + radius * np.cos(theta_grid)
        Z = cz + radius * np.sin(theta_grid)
    return go.Surface(
        x=X, y=Y, z=Z, showscale=False, surfacecolor=np.zeros_like(X),
        colorscale=[[0, color], [1, color]], hoverinfo="skip", showlegend=False,
        lighting=dict(ambient=0.55, diffuse=0.75, specular=0.25, roughness=0.5),
    )


def _axis_offset(center, axis, delta):
    cx, cy, cz = center
    if axis == "x":
        return (cx + delta, cy, cz)
    if axis == "z":
        return (cx, cy, cz + delta)
    return (cx, cy + delta, cz)


def _coil_like_mesh(base_center, axis, outer_r, inner_r, length, color, straps=3):
    """A hollow-eyed cylinder (coil or strip pallet's steel roll): outer
    tube + a steel end cap at each end + a dark bore disk layered just
    in front of each cap to read as the hollow "eye", plus a few darker
    strap bands around the circumference like the reference photos."""
    traces = [_cylinder_tube(base_center, axis, outer_r, length, color)]
    end_a = base_center
    end_b = _axis_offset(base_center, axis, length)
    for end, sign in ((end_a, -1), (end_b, 1)):
        traces.append(_disk_mesh(end, axis, outer_r, color))
        bore_center = _axis_offset(end, axis, sign * length * 0.003)
        traces.append(_disk_mesh(bore_center, axis, inner_r, BORE_COLOR))

    for frac in np.linspace(0.18, 0.82, straps):
        strap_center = _axis_offset(base_center, axis, length * frac)
        traces.append(_cylinder_tube(
            _axis_offset(strap_center, axis, -length * 0.015), axis,
            outer_r * 1.015, length * 0.03, STRAP_COLOR,
        ))
    return traces


def _wheel(center, radius, width):
    """A simple tire: a short, thick disc with its axle along Y (across
    the truck's width) - used for both the tractor cab and trailer."""
    return _cylinder_tube(
        (center[0], center[1] - width / 2, center[2]), "y", radius, width, "#1c1c1c",
    ), _disk_mesh((center[0], center[1] - width / 2, center[2]), "y", radius, "#1c1c1c"), \
        _disk_mesh((center[0], center[1] + width / 2, center[2]), "y", radius, "#1c1c1c")


def _truck_cab_traces():
    """A simple tractor-unit cab in front of the trailer (negative x),
    plus a couple of wheel pairs under the cab and trailer, so the scene
    reads as a complete truck rather than a bare flatbed."""
    W, H = config.TRUCK_WIDTH_MM, config.TRUCK_HEIGHT_MM
    cab_length = 2200.0
    cab_x0 = -cab_length - 300.0
    traces = []

    # Lower cab body + raised cabin/windshield box.
    traces.append(_box_mesh(cab_x0, 80, -80, cab_length, W - 160, 1550, "#9b1c1c"))
    traces.append(_box_mesh(cab_x0 + cab_length * 0.1, 150, 1470, cab_length * 0.75, W - 300, 950, "#b32424"))
    traces.append(_box_mesh(cab_x0 + cab_length * 0.72, 180, 1650, cab_length * 0.22, W - 360, 650, "#dce6ec", opacity=0.75))

    # Wheels hang below the bed/chassis underside (z=-80), not inside the
    # cargo space - center them so each wheel's top just touches z=-80.
    wheel_r, wheel_w = 500.0, 280.0
    wheel_z = -80.0 - wheel_r
    for wx in (cab_x0 + 550, cab_x0 + cab_length - 500, -400):
        for wy in (90, W - 90):
            tube, cap_a, cap_b = _wheel((wx, wy, wheel_z), wheel_r, wheel_w)
            traces += [tube, cap_a, cap_b]

    # A couple of trailer wheel pairs near the rear underside.
    L = config.TRUCK_LENGTH_MM
    for wx in (L - 1600, L - 1050):
        for wy in (90, W - 90):
            tube, cap_a, cap_b = _wheel((wx, wy, wheel_z), wheel_r, wheel_w)
            traces += [tube, cap_a, cap_b]

    return traces


def _truck_frame_traces():
    L, W, H = config.TRUCK_LENGTH_MM, config.TRUCK_WIDTH_MM, config.TRUCK_HEIGHT_MM
    traces = [_box_mesh(0, 0, -80, L, W, 80, "#3f3f3f")]
    traces += _truck_cab_traces()

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


def _pallet_traces(p):
    """One placed pallet (p is a backend.truck_loading.Placement) as a
    wood-pallet base plus its commodity on top, matching its real shape."""
    traces = [_box_mesh(p.x_mm, p.y_mm, p.z_mm, p.length_mm, p.width_mm, PALLET_WOOD_HEIGHT_MM, WOOD_COLOR)]
    color = PALLET_COLORS.get(p.kind, "#999999")
    top_z = p.z_mm + PALLET_WOOD_HEIGHT_MM

    if p.kind == "coil":
        outer_r = min(p.width_mm, p.length_mm) / 2 * 0.86
        inner_r = outer_r * 0.35
        axis_len = p.length_mm * 0.8
        start = (p.x_mm + (p.length_mm - axis_len) / 2, p.y_mm + p.width_mm / 2, top_z + outer_r)
        traces += _coil_like_mesh(start, "x", outer_r, inner_r, axis_len, color)
    elif p.kind == "strips":
        outer_r = min(p.width_mm, p.length_mm) / 2 * 0.86
        inner_r = outer_r * 0.3
        axis_len = max(p.height_mm - PALLET_WOOD_HEIGHT_MM, 200.0)
        start = (p.x_mm + p.length_mm / 2, p.y_mm + p.width_mm / 2, top_z)
        traces += _coil_like_mesh(start, "z", outer_r, inner_r, axis_len, color, straps=2)
    else:  # sheet (possibly a stack of several physical layers)
        members = p.members if (p.members and len(p.members) > 1) else [None]
        layer_h = (p.height_mm) / len(members) if members else p.height_mm
        for idx in range(len(members)):
            z0 = top_z + idx * layer_h
            traces.append(_box_mesh(p.x_mm, p.y_mm, z0, p.length_mm, p.width_mm, layer_h * 0.9, color))
        # a faint wrap film over the whole stack, like the reference photo
        wrap_z0, wrap_h = top_z, layer_h * len(members)
        traces.append(_box_mesh(
            p.x_mm - 15, p.y_mm - 15, wrap_z0 - 5, p.length_mm + 30, p.width_mm + 30, wrap_h + 10,
            "#ffffff", opacity=0.12,
        ))

    cx = p.x_mm + p.length_mm / 2
    cy = p.y_mm + p.width_mm / 2
    label_z = top_z + p.height_mm - PALLET_WOOD_HEIGHT_MM + 60

    traces.append(go.Scatter3d(
        x=[cx], y=[cy], z=[p.z_mm + p.height_mm / 2],
        mode="markers", marker=dict(size=1, opacity=0),
        hovertext=[f"{p.label}<br>{p.weight_kg:.0f} kg"], hoverinfo="text", showlegend=False,
    ))
    traces.append(go.Scatter3d(
        x=[cx], y=[cy], z=[label_z],
        mode="text", text=[f"{p.weight_kg:.0f} kg"],
        textfont=dict(color="black", size=12, family="Arial Black"),
        showlegend=False, hoverinfo="skip",
    ))
    return traces


def build_truck_figure(placements=None) -> go.Figure:
    placements = placements or []
    fig = go.Figure()

    for trace in _truck_frame_traces():
        fig.add_trace(trace)

    for p in placements:
        for trace in _pallet_traces(p):
            fig.add_trace(trace)

    L, W, H = config.TRUCK_LENGTH_MM, config.TRUCK_WIDTH_MM, config.TRUCK_HEIGHT_MM
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Length (mm)", range=[-3200, L + 800]),
            yaxis=dict(title="Width (mm)", range=[-800, W + 800]),
            zaxis=dict(title="Height (mm)", range=[-1300, H + 1200]),
            aspectmode="data",
            camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=650,
        showlegend=False,
    )
    return fig
