"""
Plotly HUD Theme and Dynamic Team Color Resolver for PitWall AI.
Implements the dark HUD theme standard with canvas background #0B0F17,
panel background #121824, and WCAG AA compliant text contrast.
Provides teammate color collision handling.
"""

from typing import Any, Dict, Optional, Tuple
import fastf1.plotting

# Official Dark HUD Theme Palette
HUD_BG_COLOR = "#0B0F17"
HUD_SURFACE_COLOR = "#121824"
HUD_BORDER_COLOR = "#1E293B"
HUD_GRID_COLOR = "#1E293B"
HUD_ZERO_LINE_COLOR = "#334155"
HUD_TEXT_MUTED = "#94A3B8"
HUD_TEXT_NORMAL = "#E2E8F0"
HUD_TEXT_BRIGHT = "#FFFFFF"
HUD_ACCENT_RED = "#E10600"
HUD_ACCENT_CYAN = "#38BDF8"
HUD_ACCENT_YELLOW = "#FACC15"

# Fallback team colors in hex if FastF1 session does not contain specific mapping
FALLBACK_TEAM_COLORS = {
    "Red Bull Racing": "#3671C6",
    "Ferrari": "#E80020",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#0093CC",
    "Williams": "#64C4FF",
    "RB": "#6692FF",
    "AlphaTauri": "#5E8FAA",
    "Kick Sauber": "#52E252",
    "Alfa Romeo": "#C92D4B",
    "Haas": "#B6BABD",
    "Renault": "#FFF500",
    "Racing Point": "#F596C8",
    "Toro Rosso": "#469BFF",
    "Force India": "#F596C8",
    "Lotus": "#E8C838",
    "Brawn": "#B8FD38",
}


def get_hud_layout_template() -> Dict[str, Any]:
    """
    Returns standard Plotly layout dictionary conforming to PitWall dark HUD guidelines.
    """
    return {
        "paper_bgcolor": HUD_BG_COLOR,
        "plot_bgcolor": HUD_BG_COLOR,
        "font": {
            "family": "Inter, system-ui, -apple-system, sans-serif",
            "size": 12,
            "color": HUD_TEXT_NORMAL,
        },
        "xaxis": {
            "gridcolor": HUD_GRID_COLOR,
            "zerolinecolor": HUD_ZERO_LINE_COLOR,
            "color": HUD_TEXT_MUTED,
            "tickfont": {"color": HUD_TEXT_MUTED},
            "linecolor": HUD_BORDER_COLOR,
            "showline": True,
        },
        "yaxis": {
            "gridcolor": HUD_GRID_COLOR,
            "zerolinecolor": HUD_ZERO_LINE_COLOR,
            "color": HUD_TEXT_MUTED,
            "tickfont": {"color": HUD_TEXT_MUTED},
            "linecolor": HUD_BORDER_COLOR,
            "showline": True,
        },
        "legend": {
            "bgcolor": "rgba(18, 24, 36, 0.8)",
            "bordercolor": HUD_BORDER_COLOR,
            "borderwidth": 1,
            "font": {"color": HUD_TEXT_NORMAL},
        },
        "margin": {"l": 50, "r": 20, "t": 50, "b": 40},
        "hoverlabel": {
            "bgcolor": HUD_SURFACE_COLOR,
            "bordercolor": HUD_BORDER_COLOR,
            "font": {"color": HUD_TEXT_BRIGHT, "family": "Inter, sans-serif"},
        },
    }


def calculate_luminance(hex_color: str) -> float:
    """Calculates relative luminance of a hex color."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return 0.5
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0

        def srgb_to_lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)
    except Exception:
        return 0.5


def resolve_team_color(team_name: str, session: Optional[Any] = None) -> str:
    """
    Retrieves official team color dynamically via fastf1.plotting.get_team_color().
    Falls back to curated team color dictionary if session is unavailable.
    Ensures sufficient luminance against #0B0F17 HUD background.
    """
    color = None
    if session is not None:
        try:
            color = fastf1.plotting.get_team_color(team_name, session=session)
        except Exception:
            pass

    if not color:
        # Check fallback dictionary
        for k, v in FALLBACK_TEAM_COLORS.items():
            if k.lower() in team_name.lower() or team_name.lower() in k.lower():
                color = v
                break

    if not color:
        color = HUD_ACCENT_CYAN  # Default bright cyan

    # Validate contrast against #0B0F17:
    lum = calculate_luminance(color)
    if lum < 0.08:
        # Brighten dark colors
        color = "#60A5FA"

    return color


def get_driver_trace_styles(
    color_1: str,
    color_2: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resolves line trace styles (color, dash) for two drivers.
    If both drivers share the same team color (teammates), automatically
    distinguishes Driver 2 with a dashed line and high-contrast secondary accent.
    """
    c1 = color_1.upper()
    c2 = color_2.upper()

    style_1 = {"color": color_1, "dash": "solid", "width": 2.2}

    if c1 == c2:
        # Teammate collision: style Driver 2 with dashed line and high-contrast accent
        alt_color = HUD_ACCENT_YELLOW if c1 != HUD_ACCENT_YELLOW else HUD_ACCENT_CYAN
        style_2 = {"color": alt_color, "dash": "dash", "width": 2.0}
    else:
        style_2 = {"color": color_2, "dash": "solid", "width": 2.2}

    return style_1, style_2
