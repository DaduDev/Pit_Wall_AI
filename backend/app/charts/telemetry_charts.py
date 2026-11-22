"""
Multi-Panel Telemetry Chart Builder and Zoomed GPS Track Mini-Map Builder for PitWall AI.
Implements:
- 5-panel synchronized telemetry chart (Speed, Delta, Throttle, Brake, Gear) sharing distance X-axis
- Vertical dashed apex line across subplots
- Zoomed GPS corner mini-map with 1:1 aspect ratio colored by faster driver through each segment
- Entry / Apex / Exit markers
- Dark HUD styling (#0B0F17) with teammate collision resolution
"""

from typing import Any, Dict, List, Optional
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from backend.app.charts.plotly_theme import (
    HUD_BG_COLOR,
    HUD_BORDER_COLOR,
    HUD_GRID_COLOR,
    HUD_SURFACE_COLOR,
    HUD_TEXT_BRIGHT,
    HUD_TEXT_MUTED,
    HUD_TEXT_NORMAL,
    HUD_ZERO_LINE_COLOR,
    get_driver_trace_styles,
    get_hud_layout_template,
)


def build_corner_comparison_figure(
    grid_distance: np.ndarray,
    data_a: Dict[str, np.ndarray],
    data_b: Dict[str, np.ndarray],
    delta_trace: np.ndarray,
    meta_a: Dict[str, Any],
    meta_b: Dict[str, Any],
    corner_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Builds a 5-panel synchronized Plotly chart:
    - Row 1: Speed (km/h)
    - Row 2: Corner Delta (s, relative to Driver A, zeroed at corner entry)
    - Row 3: Throttle (%)
    - Row 4: Brake (%)
    - Row 5: Gear (1-8)
    """
    driver_a = meta_a["driver_code"]
    driver_b = meta_b["driver_code"]
    color_a = meta_a.get("team_color", "#38BDF8")
    color_b = meta_b.get("team_color", "#E80020")

    style_a, style_b = get_driver_trace_styles(color_a, color_b)

    turn_num = corner_info.get("turn_number", 0)
    nickname = corner_info.get("nickname", f"Turn {turn_num}")
    apex_dist = corner_info.get("distance_m", grid_distance[len(grid_distance) // 2])

    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.32, 0.20, 0.18, 0.15, 0.15],
        subplot_titles=(
            f"Speed (km/h)",
            f"Delta: {driver_b} vs {driver_a} (s)",
            f"Throttle (%)",
            f"Brake (%)",
            f"Gear",
        ),
    )

    x_vals = grid_distance.tolist()

    # 1. Speed (Row 1)
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_a["Speed"].tolist(),
            name=f"{driver_a} (Lap {meta_a.get('lap_number', '')})",
            line=dict(color=style_a["color"], width=style_a["width"], dash=style_a["dash"]),
            hovertemplate=f"{driver_a}: %{{y:.1f}} km/h<extra></extra>",
            showlegend=True,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_b["Speed"].tolist(),
            name=f"{driver_b} (Lap {meta_b.get('lap_number', '')})",
            line=dict(color=style_b["color"], width=style_b["width"], dash=style_b["dash"]),
            hovertemplate=f"{driver_b}: %{{y:.1f}} km/h<extra></extra>",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    # 2. Delta (Row 2) - Zeroed at corner entry
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=delta_trace.tolist(),
            name=f"Delta ({driver_b} - {driver_a})",
            line=dict(color="#F8FAFC", width=2.0),
            hovertemplate="Delta: %{y:+.3f}s<extra></extra>",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # 3. Throttle (Row 3)
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_a["Throttle"].tolist(),
            name=f"{driver_a} Throttle",
            line=dict(color=style_a["color"], width=style_a["width"], dash=style_a["dash"]),
            hovertemplate=f"{driver_a} Throttle: %{{y:.0f}}%<extra></extra>",
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_b["Throttle"].tolist(),
            name=f"{driver_b} Throttle",
            line=dict(color=style_b["color"], width=style_b["width"], dash=style_b["dash"]),
            hovertemplate=f"{driver_b} Throttle: %{{y:.0f}}%<extra></extra>",
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    # 4. Brake (Row 4)
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_a["Brake"].tolist(),
            name=f"{driver_a} Brake",
            line=dict(color=style_a["color"], width=style_a["width"], dash=style_a["dash"]),
            hovertemplate=f"{driver_a} Brake: %{{y:.0f}}%<extra></extra>",
            showlegend=False,
        ),
        row=4,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_b["Brake"].tolist(),
            name=f"{driver_b} Brake",
            line=dict(color=style_b["color"], width=style_b["width"], dash=style_b["dash"]),
            hovertemplate=f"{driver_b} Brake: %{{y:.0f}}%<extra></extra>",
            showlegend=False,
        ),
        row=4,
        col=1,
    )

    # 5. Gear (Row 5)
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_a["nGear"].tolist(),
            name=f"{driver_a} Gear",
            line=dict(color=style_a["color"], width=style_a["width"], dash=style_a["dash"]),
            hovertemplate=f"{driver_a} Gear: %{{y}}<extra></extra>",
            showlegend=False,
        ),
        row=5,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=data_b["nGear"].tolist(),
            name=f"{driver_b} Gear",
            line=dict(color=style_b["color"], width=style_b["width"], dash=style_b["dash"]),
            hovertemplate=f"{driver_b} Gear: %{{y}}<extra></extra>",
            showlegend=False,
        ),
        row=5,
        col=1,
    )

    # Add vertical dashed line at apex across all subplots
    for r in range(1, 6):
        fig.add_vline(
            x=apex_dist,
            line_width=1.5,
            line_dash="dash",
            line_color="#E10600",
            annotation_text="Apex" if r == 1 else None,
            annotation_position="top right" if r == 1 else None,
            annotation_font=dict(color="#E10600", size=10, family="Inter, monospace"),
            row=r,
            col=1,
        )

    # Title & Subtitle
    title_main = f"<b>{driver_a} vs {driver_b} — {nickname} (Turn {turn_num})</b>"
    subtitle = (
        f"{meta_a.get('year', '')} {meta_a.get('event_name', '')} | {meta_a.get('session_type', 'Qualifying')} | "
        f"{driver_a} (Lap {meta_a.get('lap_number', '')}, {meta_a.get('compound', '')}) vs "
        f"{driver_b} (Lap {meta_b.get('lap_number', '')}, {meta_b.get('compound', '')})"
    )

    base_layout = get_hud_layout_template()
    fig.update_layout(
        paper_bgcolor=HUD_BG_COLOR,
        plot_bgcolor=HUD_BG_COLOR,
        font=base_layout["font"],
        title=dict(
            text=f"{title_main}<br><span style='font-size:11px;color:{HUD_TEXT_MUTED}'>{subtitle}</span>",
            x=0.03,
            y=0.98,
            xanchor="left",
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=0.98,
            bgcolor="rgba(18, 24, 36, 0.85)",
            bordercolor=HUD_BORDER_COLOR,
            borderwidth=1,
            font=dict(color=HUD_TEXT_BRIGHT, size=11),
        ),
        hovermode="x unified",
        margin=dict(l=55, r=25, t=90, b=45),
        height=620,
    )

    # Apply axis styling across all subplots
    fig.update_xaxes(
        gridcolor=HUD_GRID_COLOR,
        zerolinecolor=HUD_ZERO_LINE_COLOR,
        color=HUD_TEXT_MUTED,
        linecolor=HUD_BORDER_COLOR,
        tickfont=dict(color=HUD_TEXT_MUTED, size=10),
    )
    fig.update_yaxes(
        gridcolor=HUD_GRID_COLOR,
        zerolinecolor=HUD_ZERO_LINE_COLOR,
        color=HUD_TEXT_MUTED,
        linecolor=HUD_BORDER_COLOR,
        tickfont=dict(color=HUD_TEXT_MUTED, size=10),
    )

    # Bottom X axis label
    fig.update_xaxes(title_text="Track Distance (meters)", row=5, col=1)

    # Format subplot titles to be muted and smaller
    for annotation in fig["layout"]["annotations"]:
        if annotation["text"] not in ["Apex"]:
            annotation["font"] = dict(color=HUD_TEXT_MUTED, size=11, family="Inter, monospace")

    return fig.to_plotly_json()


def build_corner_minimap_figure(
    grid_distance: np.ndarray,
    data_a: Dict[str, np.ndarray],
    data_b: Dict[str, np.ndarray],
    meta_a: Dict[str, Any],
    meta_b: Dict[str, Any],
    corner_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Builds a zoomed GPS corner mini-map:
    - 1:1 aspect ratio (scaleanchor='x', scaleratio=1)
    - Ticks and grids hidden
    - Track line segmented and colored by which driver is faster through each 1-meter step
    - Entry, Apex, and Exit marker annotations
    """
    driver_a = meta_a["driver_code"]
    driver_b = meta_b["driver_code"]
    color_a = meta_a.get("team_color", "#38BDF8")
    color_b = meta_b.get("team_color", "#E80020")

    style_a, style_b = get_driver_trace_styles(color_a, color_b)

    x_coords = data_a["X"]
    y_coords = data_a["Y"]
    speeds_a = data_a["Speed"]
    speeds_b = data_b["Speed"]

    # In case GPS coordinates are 0 (e.g. mock or missing GPS), generate synthetic curvature based on apex
    if np.all(x_coords == 0) and np.all(y_coords == 0):
        t = np.linspace(-np.pi / 2, np.pi / 2, len(grid_distance))
        x_coords = 200.0 * np.sin(t)
        y_coords = 200.0 * (1.0 - np.cos(t))

    fig = go.Figure()

    # Partition track into segments colored by faster driver
    faster_mask = speeds_a >= speeds_b  # True = Driver A faster, False = Driver B faster

    # Render segments in chunks
    chunk_start = 0
    while chunk_start < len(grid_distance) - 1:
        current_faster = faster_mask[chunk_start]
        chunk_end = chunk_start + 1
        while chunk_end < len(grid_distance) and faster_mask[chunk_end] == current_faster:
            chunk_end += 1

        seg_x = x_coords[chunk_start : min(chunk_end + 1, len(x_coords))]
        seg_y = y_coords[chunk_start : min(chunk_end + 1, len(y_coords))]
        seg_color = style_a["color"] if current_faster else style_b["color"]
        seg_driver = driver_a if current_faster else driver_b

        fig.add_trace(
            go.Scatter(
                x=seg_x.tolist(),
                y=seg_y.tolist(),
                mode="lines",
                line=dict(color=seg_color, width=4.0),
                name=f"{seg_driver} Faster",
                hoverinfo="skip",
                showlegend=False,
            )
        )
        chunk_start = chunk_end

    # Dummy traces for legend
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=style_a["color"], width=4.0),
            name=f"{driver_a} Faster",
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=style_b["color"], width=4.0),
            name=f"{driver_b} Faster",
            showlegend=True,
        )
    )

    # Entry, Apex, and Exit markers
    mid_idx = len(x_coords) // 2
    markers_x = [x_coords[0], x_coords[mid_idx], x_coords[-1]]
    markers_y = [y_coords[0], y_coords[mid_idx], y_coords[-1]]
    marker_labels = ["Entry", f"Apex (T{corner_info.get('turn_number', 0)})", "Exit"]
    marker_colors = ["#22C55E", "#E10600", "#38BDF8"]

    fig.add_trace(
        go.Scatter(
            x=markers_x,
            y=markers_y,
            mode="markers+text",
            marker=dict(size=9, color=marker_colors, line=dict(color="#FFFFFF", width=1.5)),
            text=marker_labels,
            textposition=["top center", "bottom center", "top center"],
            textfont=dict(color="#FFFFFF", size=10, family="Inter, monospace"),
            name="Key Points",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    nickname = corner_info.get("nickname", f"Turn {corner_info.get('turn_number', '')}")
    fig.update_layout(
        paper_bgcolor=HUD_BG_COLOR,
        plot_bgcolor=HUD_BG_COLOR,
        title=dict(
            text=f"<b>GPS Track Mini-Map — {nickname}</b><br><span style='font-size:10px;color:{HUD_TEXT_MUTED}'>Colored by faster driver segment</span>",
            x=0.04,
            y=0.96,
            xanchor="left",
            yanchor="top",
            font=dict(color=HUD_TEXT_BRIGHT, size=12),
        ),
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            showline=False,
            scaleanchor="x",
            scaleratio=1,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(18, 24, 36, 0.9)",
            bordercolor=HUD_BORDER_COLOR,
            borderwidth=1,
            font=dict(color=HUD_TEXT_BRIGHT, size=10),
        ),
        margin=dict(l=15, r=15, t=55, b=25),
        height=320,
    )

    return fig.to_plotly_json()
