"""
Unit tests for Dark HUD Plotly theme template and team colors.
"""

from backend.app.charts.plotly_theme import (
    get_hud_layout_template,
    resolve_team_color,
    calculate_luminance,
    HUD_BG_COLOR,
)


def test_hud_layout_template():
    template = get_hud_layout_template()
    assert template["paper_bgcolor"] == HUD_BG_COLOR
    assert template["plot_bgcolor"] == HUD_BG_COLOR
    assert template["font"]["color"] == "#E2E8F0"
    assert template["xaxis"]["gridcolor"] == "#1E293B"


def test_resolve_team_color_fallbacks():
    # Red Bull
    rb_color = resolve_team_color("Red Bull Racing")
    assert rb_color == "#3671C6"
    assert calculate_luminance(rb_color) > 0.08

    # Ferrari
    fer_color = resolve_team_color("Ferrari")
    assert fer_color == "#E80020"

    # Mercedes
    merc_color = resolve_team_color("Mercedes")
    assert merc_color == "#27F4D2"

    # Unknown team fallback
    unk_color = resolve_team_color("Unknown Vintage Team")
    assert unk_color.startswith("#")
