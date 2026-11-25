"""
Plotly Strategy and Tyre Stint Degradation Chart Builders for PitWall AI.
Implements:
- 2-subplot synchronized dark HUD layout (#0B0F17)
  1. Main panel: Clean lap times (scatter points + dashed linear trendline per stint) over Race Lap Number,
     with vertical dashed pit-stop markers showing compound switches.
  2. Secondary compact strip: Horizontal Stint Timeline showing each driver's compound sequence and stint lengths.
- Official Pirelli compound colors:
  SOFT #FF3333, MEDIUM #FFD700, HARD #F0F0F0, INTERMEDIATE #39B54A, WET #00AEEF.
- Multi-driver differentiation via marker symbols and line dash styles.
- Zero-hallucination math grounded in clean lap times and linear regression slopes.
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
    PIRELLI_COMPOUND_COLORS,
    get_hud_layout_template,
    resolve_team_color,
)

FALLBACK_DRIVER_TEAMS = {
    "VER": "Red Bull Racing", "PER": "Red Bull Racing",
    "HAM": "Mercedes", "RUS": "Mercedes",
    "LEC": "Ferrari", "SAI": "Ferrari",
    "NOR": "McLaren", "PIA": "McLaren",
    "ALO": "Aston Martin", "STR": "Aston Martin",
    "GAS": "Alpine", "OCO": "Alpine",
    "TSU": "RB", "RIC": "RB", "LAW": "RB",
    "ALB": "Williams", "SAR": "Williams", "COL": "Williams",
    "BOT": "Kick Sauber", "ZHO": "Kick Sauber",
    "HUL": "Haas", "MAG": "Haas",
}

DRIVER_MARKER_SYMBOLS = ["circle", "diamond", "square", "triangle-up", "star"]
DRIVER_LINE_DASHES = ["solid", "dash", "dot", "dashdot", "longdash"]


def build_tyre_degradation_figure(
    drivers_data: Dict[str, Dict[str, Any]],
    event_metadata: Dict[str, Any],
    summary_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds a 2-subplot synchronized Plotly figure for tyre stint degradation analysis.
    - Row 1: Race Lap vs Lap Time (s) with clean lap scatter, outlier markers, trendlines, and pit stops.
    - Row 2: Horizontal Stint Timeline per driver colored by compound.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.72, 0.28],
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=(
            "<b>CLEAN LAP PACE & OBSERVED TYRE DEGRADATION (s/lap)</b>",
            "<b>RACE STINT STRATEGY TIMELINE</b>",
        ),
    )

    all_clean_times: List[float] = []
    all_laps: List[int] = []
    driver_codes = list(drivers_data.keys())

    # -------------------------------------------------------------
    # 1. Main Panel (Row 1): Lap Times, Trendlines, Pit Stops
    # -------------------------------------------------------------
    for d_idx, (drv_code, d_info) in enumerate(drivers_data.items()):
        marker_symbol = DRIVER_MARKER_SYMBOLS[d_idx % len(DRIVER_MARKER_SYMBOLS)]
        line_dash = DRIVER_LINE_DASHES[d_idx % len(DRIVER_LINE_DASHES)]
        team_name = d_info.get("team_name", drv_code)
        stints = d_info.get("stints", [])
        clean_laps = d_info.get("clean_laps", [])
        outliers = d_info.get("outliers", [])
        pit_stops = d_info.get("pit_stops", [])

        # Plot each stint's clean laps and regression trendline
        for stint in stints:
            stint_num = stint["stint_number"]
            compound = (stint.get("compound") or "UNKNOWN").upper()
            color = PIRELLI_COMPOUND_COLORS.get(compound, PIRELLI_COMPOUND_COLORS["UNKNOWN"])

            stint_clean = [l for l in clean_laps if l.get("stint_number") == stint_num]
            if not stint_clean:
                continue

            laps_x = [l["lap_number"] for l in stint_clean]
            times_y = [l["lap_duration"] for l in stint_clean]
            ages_z = [l.get("tyre_age", l["lap_number"]) for l in stint_clean]
            all_clean_times.extend(times_y)
            all_laps.extend(laps_x)

            deg_slope = stint.get("deg_slope_sec_per_lap", 0.0)
            avg_pace = stint.get("avg_clean_pace_s", 0.0)

            slope_str = f"{deg_slope:+.3f}s/lap" if deg_slope != 0.0 else "flat"
            legend_label = f"{drv_code} — {compound} (S{stint_num}): {slope_str}"

            # Scatter points for clean laps
            custom_data = [
                [drv_code, compound, stint_num, age, f"{t:.3f}s"]
                for age, t in zip(ages_z, times_y)
            ]
            fig.add_trace(
                go.Scatter(
                    x=laps_x,
                    y=times_y,
                    mode="markers",
                    name=legend_label,
                    marker=dict(
                        symbol=marker_symbol,
                        size=7,
                        color=color,
                        line=dict(color="#0B0F17", width=1),
                    ),
                    customdata=custom_data,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b> (Lap %{x})<br>"
                        "Time: <b>%{customdata[4]}</b><br>"
                        "Compound: <b>%{customdata[1]}</b> (Stint %{customdata[2]})<br>"
                        "Tyre Age: %{customdata[3]} laps"
                        "<extra></extra>"
                    ),
                    legendgroup=f"{drv_code}_S{stint_num}",
                ),
                row=1,
                col=1,
            )

            # Linear regression trendline (if >= 3 clean laps)
            if len(laps_x) >= 3 and stint.get("slope_coords"):
                x_trend, y_trend = stint["slope_coords"]
                fig.add_trace(
                    go.Scatter(
                        x=x_trend,
                        y=y_trend,
                        mode="lines",
                        name=f"{legend_label} trend",
                        line=dict(
                            color=color,
                            width=2,
                            dash=line_dash,
                        ),
                        hoverinfo="skip",
                        showlegend=False,
                        legendgroup=f"{drv_code}_S{stint_num}",
                    ),
                    row=1,
                    col=1,
                )

        # Plot excluded outliers (hollow dimmed markers)
        if outliers:
            out_x = [o["lap_number"] for o in outliers]
            out_y = [o["lap_duration"] for o in outliers]
            out_reasons = [o.get("reason", "Outlier") for o in outliers]
            fig.add_trace(
                go.Scatter(
                    x=out_x,
                    y=out_y,
                    mode="markers",
                    name=f"{drv_code} Excluded Laps",
                    marker=dict(
                        symbol="circle-open",
                        size=6,
                        color="#64748B",
                        line=dict(color="#64748B", width=1.5),
                    ),
                    customdata=[[drv_code, r, f"{t:.3f}s"] for r, t in zip(out_reasons, out_y)],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b> Lap %{x}: <b>%{customdata[2]}</b><br>"
                        "Status: <i>%{customdata[1]}</i>"
                        "<extra></extra>"
                    ),
                    showlegend=d_idx == 0,
                    opacity=0.45,
                ),
                row=1,
                col=1,
            )

        # Pit stop dashed vertical annotations
        for pit_lap in pit_stops:
            fig.add_vline(
                x=pit_lap,
                line_width=1,
                line_dash="dot",
                line_color="#E10600",
                opacity=0.6,
                row=1,
                col=1,
            )
            fig.add_annotation(
                x=pit_lap,
                y=max(all_clean_times) if all_clean_times else 90.0,
                yref="y",
                text=f"<b>{drv_code} PIT (L{pit_lap})</b>",
                showarrow=False,
                yshift=12 + (d_idx * 14),
                font=dict(color="#F87171", size=9, family="monospace"),
                bgcolor="#121824",
                bordercolor="#1E293B",
                row=1,
                col=1,
            )

    # -------------------------------------------------------------
    # 2. Secondary Panel (Row 2): Horizontal Stint Timeline
    # -------------------------------------------------------------
    for d_idx, (drv_code, d_info) in enumerate(drivers_data.items()):
        stints = d_info.get("stints", [])
        for stint in stints:
            stint_num = stint["stint_number"]
            compound = (stint.get("compound") or "UNKNOWN").upper()
            color = PIRELLI_COMPOUND_COLORS.get(compound, PIRELLI_COMPOUND_COLORS["UNKNOWN"])
            lap_start = stint["lap_start"]
            lap_end = stint["lap_end"]
            stint_len = max(1, lap_end - lap_start + 1)
            deg_val = stint.get("deg_slope_sec_per_lap", 0.0)

            # Horizontal bar trace per stint segment
            fig.add_trace(
                go.Bar(
                    y=[drv_code],
                    x=[stint_len],
                    base=[lap_start - 0.5],
                    orientation="h",
                    name=f"{compound} (Stint {stint_num})",
                    marker=dict(
                        color=color,
                        line=dict(color="#0B0F17", width=1.5),
                    ),
                    text=f"<b>{compound[:4]}</b> ({stint_len}L)",
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(
                        color="#0B0F17" if compound in ("MEDIUM", "HARD") else "#FFFFFF",
                        size=10,
                        family="monospace",
                    ),
                    customdata=[[drv_code, stint_num, compound, lap_start, lap_end, stint_len, f"{deg_val:+.3f}s/lap"]],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b> — Stint %{customdata[1]}: <b>%{customdata[2]}</b><br>"
                        "Laps %{customdata[3]} to %{customdata[4]} (%{customdata[5]} laps)<br>"
                        "Degradation Rate: <b>%{customdata[6]}</b>"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

    # -------------------------------------------------------------
    # 3. Overall HUD Layout Styling
    # -------------------------------------------------------------
    event_title = f"{event_metadata.get('year', 2024)} {event_metadata.get('grand_prix', 'Grand Prix')} {event_metadata.get('session_type', 'Race')}"

    # Calculate optimal Y-axis bounds for clean lap times
    if all_clean_times:
        y_min = max(50.0, min(all_clean_times) - 1.0)
        y_max = min(all_clean_times) + 6.0  # Show clean window without stretching to outlier scale
        if max(all_clean_times) < y_max:
            y_max = max(all_clean_times) + 1.0
    else:
        y_min = 70.0
        y_max = 95.0

    max_lap = max(all_laps) if all_laps else 60

    fig.update_layout(
        paper_bgcolor=HUD_BG_COLOR,
        plot_bgcolor=HUD_BG_COLOR,
        barmode="stack",
        hovermode="closest",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=HUD_TEXT_NORMAL, family="monospace"),
            bgcolor="rgba(18, 24, 36, 0.8)",
            bordercolor=HUD_BORDER_COLOR,
            borderwidth=1,
        ),
        font=dict(family="Inter, system-ui, sans-serif", color=HUD_TEXT_NORMAL),
        margin=dict(l=60, r=30, t=75, b=45),
    )

    # Subplot 1 axes
    fig.update_xaxes(
        gridcolor=HUD_GRID_COLOR,
        zeroline=False,
        range=[0, max_lap + 2],
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="<b>Lap Time (s)</b>",
        gridcolor=HUD_GRID_COLOR,
        zeroline=False,
        range=[y_min, y_max],
        tickformat=".1f",
        row=1,
        col=1,
    )

    # Subplot 2 axes
    fig.update_xaxes(
        title_text="<b>Race Lap Number</b>",
        gridcolor=HUD_GRID_COLOR,
        zeroline=False,
        range=[0, max_lap + 2],
        dtick=5,
        row=2,
        col=1,
    )
    fig.update_yaxes(
        title_text="<b>Driver</b>",
        gridcolor=HUD_GRID_COLOR,
        zeroline=False,
        row=2,
        col=1,
    )

    # Subplot titles font styling
    for ann in fig["layout"]["annotations"]:
        ann["font"] = dict(color=HUD_TEXT_BRIGHT, size=11, family="monospace")

    spec = fig.to_plotly_json()
    spec["chart_type"] = "tyre_degradation"

    standardized_drivers = []
    for drv_code, d_info in drivers_data.items():
        team_name = d_info.get("team_name") or FALLBACK_DRIVER_TEAMS.get(drv_code, drv_code)
        team_color = resolve_team_color(team_name)
        stints = d_info.get("stints", [])
        primary_comp = stints[0].get("compound") if stints else None
        d_entry: Dict[str, Any] = {
            "code": drv_code,
            "name": team_name,
            "color": team_color,
        }
        if primary_comp and primary_comp != "UNKNOWN":
            d_entry["compound"] = primary_comp
        standardized_drivers.append(d_entry)

    spec["metadata"] = {
        "domain": "telemetry",
        "year": int(event_metadata.get("year", 2024)),
        "grand_prix": event_metadata.get("grand_prix", "Grand Prix"),
        "session_name": event_metadata.get("session_type", "Race"),
        "mode_label": "Tyre Degradation & Stint Strategy",
        "drivers": standardized_drivers,
        "track_status": "DRY",
        "event_name": event_metadata.get("grand_prix"),
        "session_type": event_metadata.get("session_type"),
        "metrics": summary_metrics or {},
    }
    return spec
