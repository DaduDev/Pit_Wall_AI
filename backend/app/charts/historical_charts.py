"""
Historical Chart Builders for PitWall AI.
Constructs Plotly JSON specifications for Bar charts, Line charts,
Horizontal ranking charts, and classification tables adhering to the #0B0F17 dark HUD standard.
"""

import re
from typing import Any, Dict, List, Optional
from backend.app.charts.plotly_theme import get_hud_layout_template, HUD_ACCENT_RED


def build_horizontal_ranking_bar_chart(
    title: str,
    categories: List[str],
    values: List[Any],
    metric_name: str = "Metric",
    row_data: Optional[List[Dict[str, Any]]] = None,
    marker_color: str = HUD_ACCENT_RED,
) -> Dict[str, Any]:
    """
    Builds a horizontal ranking bar chart (orientation='h', sorted top-to-bottom)
    with values formatted cleanly outside the bars and rich hover tooltips.
    """
    layout = get_hud_layout_template()
    metric_title = metric_name.replace("_", " ").title()

    layout.update({
        "title": {
            "text": title,
            "font": {"color": "#FFFFFF", "size": 15, "family": "Inter, sans-serif"},
            "x": 0.02,
        },
        "xaxis": {
            **layout["xaxis"],
            "title": {"text": metric_title, "font": {"color": "#94A3B8"}},
        },
        "yaxis": {
            **layout["yaxis"],
            "autorange": "reversed",  # Rank #1 displayed at the top
            "tickfont": {"color": "#FFFFFF", "size": 12, "family": "Inter, sans-serif"},
        },
        "margin": {"l": 160, "r": 70, "t": 50, "b": 40},
    })

    # Determine if metric is percentage
    is_percentage = any(kw in metric_name.lower() or kw in title.lower() for kw in ["percentage", "rate", "pct", "%"])

    formatted_texts = []
    hover_texts = []

    for idx, (cat, val) in enumerate(zip(categories, values)):
        # Format text label displayed outside the bar
        if is_percentage and isinstance(val, (int, float)):
            formatted_texts.append(f"{val:.1f}%")
        elif isinstance(val, int):
            formatted_texts.append(f"{val:,}")
        elif isinstance(val, float):
            formatted_texts.append(f"{val:.2f}" if val < 1 else f"{val:.1f}")
        else:
            formatted_texts.append(str(val) if val is not None else "")

        # Format hover tooltip
        if row_data and idx < len(row_data):
            r = row_data[idx]
            if "wins" in r and "total_starts" in r:
                hover_texts.append(
                    f"<b>{cat}</b><br>{metric_title}: {val}%<br>({r.get('wins', 0)} wins / {r.get('total_starts', 0)} starts)"
                )
            elif "wins" in r:
                hover_texts.append(f"<b>{cat}</b><br>{metric_title}: {val}<br>Wins: {r.get('wins', 0)}")
            else:
                hover_texts.append(f"<b>{cat}</b><br>{metric_title}: {val}")
        else:
            hover_texts.append(f"<b>{cat}</b><br>{metric_title}: {val}")

    trace = {
        "type": "bar",
        "orientation": "h",
        "y": categories,
        "x": values,
        "text": formatted_texts,
        "textposition": "outside",
        "textfont": {"color": "#FFFFFF", "family": "JetBrains Mono, monospace", "size": 11},
        "hovertext": hover_texts,
        "hoverinfo": "text",
        "marker": {
            "color": marker_color,
            "line": {"color": "#1E293B", "width": 1},
        },
    }

    return {
        "chart_type": "bar",
        "spec": {
            "data": [trace],
            "layout": layout,
            "config": {"responsive": True, "displayModeBar": False},
        },
        "caption": title,
    }


def build_bar_chart(
    title: str,
    x: List[Any],
    y: List[Any],
    x_title: str = "",
    y_title: str = "",
    marker_color: str = HUD_ACCENT_RED,
) -> Dict[str, Any]:
    """Builds a standard vertical bar chart."""
    layout = get_hud_layout_template()
    layout.update({
        "title": {
            "text": title,
            "font": {"color": "#FFFFFF", "size": 15, "family": "Inter, sans-serif"},
            "x": 0.02,
        },
        "xaxis": {**layout["xaxis"], "title": {"text": x_title, "font": {"color": "#94A3B8"}}},
        "yaxis": {**layout["yaxis"], "title": {"text": y_title, "font": {"color": "#94A3B8"}}},
    })

    trace = {
        "type": "bar",
        "x": x,
        "y": y,
        "marker": {
            "color": marker_color,
            "line": {"color": "#1E293B", "width": 1},
        },
        "text": [str(val) for val in y],
        "textposition": "auto",
        "textfont": {"color": "#FFFFFF", "family": "JetBrains Mono, monospace"},
        "hoverinfo": "x+y",
    }

    return {
        "chart_type": "bar",
        "spec": {
            "data": [trace],
            "layout": layout,
            "config": {"responsive": True, "displayModeBar": False},
        },
        "caption": title,
    }


def build_line_chart(
    title: str,
    x: List[Any],
    y: List[Any],
    x_title: str = "",
    y_title: str = "",
    line_color: str = "#38BDF8",
    name: str = "Series",
) -> Dict[str, Any]:
    """Builds a continuous trend line chart with markers."""
    layout = get_hud_layout_template()
    layout.update({
        "title": {
            "text": title,
            "font": {"color": "#FFFFFF", "size": 15, "family": "Inter, sans-serif"},
            "x": 0.02,
        },
        "xaxis": {**layout["xaxis"], "title": {"text": x_title, "font": {"color": "#94A3B8"}}},
        "yaxis": {**layout["yaxis"], "title": {"text": y_title, "font": {"color": "#94A3B8"}}},
    })

    trace = {
        "type": "scatter",
        "mode": "lines+markers",
        "x": x,
        "y": y,
        "name": name,
        "line": {"color": line_color, "width": 2.5, "shape": "spline"},
        "marker": {"color": line_color, "size": 6},
        "hoverinfo": "x+y",
    }

    return {
        "chart_type": "line",
        "spec": {
            "data": [trace],
            "layout": layout,
            "config": {"responsive": True, "displayModeBar": False},
        },
        "caption": title,
    }


def build_classification_table(
    title: str,
    headers: List[str],
    rows: List[List[Any]],
) -> Dict[str, Any]:
    """Builds a dark HUD Plotly table visualization."""
    layout = get_hud_layout_template()
    layout.update({
        "title": {
            "text": title,
            "font": {"color": "#FFFFFF", "size": 15, "family": "Inter, sans-serif"},
            "x": 0.02,
        },
        "margin": {"l": 20, "r": 20, "t": 50, "b": 20},
    })

    num_cols = len(headers)
    column_values = [[] for _ in range(num_cols)]
    for row in rows:
        for idx in range(num_cols):
            val = row[idx] if idx < len(row) else ""
            column_values[idx].append(str(val) if val is not None else "-")

    trace = {
        "type": "table",
        "header": {
            "values": [f"<b>{h.upper()}</b>" for h in headers],
            "fill": {"color": "#1E293B"},
            "align": "left",
            "font": {"family": "JetBrains Mono, monospace", "size": 12, "color": "#FFFFFF"},
            "height": 30,
        },
        "cells": {
            "values": column_values,
            "fill": {"color": ["#0B0F17", "#121824"]},
            "align": "left",
            "font": {"family": "Inter, sans-serif", "size": 12, "color": "#E2E8F0"},
            "height": 26,
        },
    }

    return {
        "chart_type": "table",
        "spec": {
            "data": [trace],
            "layout": layout,
            "config": {"responsive": True, "displayModeBar": False},
        },
        "caption": title,
    }


def pick_ranking_metric_column(sql: str, columns: List[str], data: List[Dict[str, Any]]) -> Optional[str]:
    """
    Picks the target value/metric column intelligently:
    1. Prefers column referenced in SQL ORDER BY.
    2. Matches prioritized keywords (percentage, rate, wins, points, avg).
    3. Excludes structural identifiers and non-ranking metrics (race_id, driver_id, total_starts).
    """
    numeric_cols = [
        c for c in columns
        if any(isinstance(row.get(c), (int, float)) for row in data[:5])
    ]
    EXCLUDED_METRICS = {
        "race_id", "driver_id", "constructor_id", "circuit_id", "status_id",
        "year", "round", "grid", "position", "rank", "stop", "lap", "number"
    }
    candidate_metrics = [c for c in numeric_cols if c.lower() not in EXCLUDED_METRICS]
    if not candidate_metrics:
        return None

    # Step 1: Check SQL ORDER BY clause
    order_by_match = re.search(r"ORDER\s+BY\s+([a-zA-Z0-9_\(\)]+)", sql, re.IGNORECASE)
    if order_by_match:
        raw_order_col = order_by_match.group(1).strip().lower()
        for c in candidate_metrics:
            if c.lower() == raw_order_col or raw_order_col.endswith(c.lower()):
                return c

    # Step 2: Match against prioritized ranking metric keywords
    PRIORITY_KEYWORDS = [
        "win_percentage", "win_pct", "win_rate", "percentage", "rate", "pct",
        "wins", "victories", "podiums", "points", "poles", "fastest_laps", "avg", "average"
    ]
    for kw in PRIORITY_KEYWORDS:
        for c in candidate_metrics:
            if kw in c.lower():
                return c

    # Step 3: If starts is present with other metrics, deprioritize starts
    non_starts = [c for c in candidate_metrics if "start" not in c.lower()]
    if non_starts:
        return non_starts[0]

    return candidate_metrics[0]


def pick_category_label_column(columns: List[str], data: List[Dict[str, Any]]) -> Optional[str]:
    """
    Selects category label column without NULLs:
    Prefers driver_name, constructor, circuit, country, or combined forename/surname.
    Never picks driver_code when a full name column exists.
    """
    lower_cols = {c.lower(): c for c in columns}

    for key in [
        "driver_name", "driver", "constructor_name", "constructor", "team",
        "circuit_name", "circuit", "grand_prix", "country"
    ]:
        if key in lower_cols:
            return lower_cols[key]

    if "forename" in lower_cols and "surname" in lower_cols:
        return "__combined_forename_surname__"

    if "surname" in lower_cols:
        return lower_cols["surname"]

    non_code_text = [
        c for c in columns
        if c.lower() != "driver_code" and any(isinstance(row.get(c), str) for row in data[:5])
    ]
    if non_code_text:
        return non_code_text[0]

    return lower_cols.get("driver_code")


def get_clean_label(row: Dict[str, Any], label_col: str, index: int) -> str:
    """Extracts and coalesces category label so Plotly never groups entries under 'None'."""
    if label_col == "__combined_forename_surname__":
        val = f"{row.get('forename', '')} {row.get('surname', '')}".strip()
    else:
        val = row.get(label_col)

    if val is None or str(val).strip() in ("", "None", "NULL"):
        if row.get("driver_name"):
            return str(row["driver_name"])
        if row.get("forename") or row.get("surname"):
            return f"{row.get('forename', '')} {row.get('surname', '')}".strip()
        if row.get("constructor"):
            return str(row["constructor"])
        if row.get("driver_id"):
            return f"Driver #{row['driver_id']}"
        return f"Entry #{index + 1}"

    return str(val).strip()


def auto_build_historical_chart(
    sql: str,
    columns: List[str],
    data: List[Dict[str, Any]],
    title_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Intelligently determines and constructs the most informative Plotly visualization
    for historical query results based on returned columns and SQL intent.
    """
    if not data or not columns:
        return None

    title = title_hint or "Formula 1 Historical Query Results"
    lower_cols = [c.lower() for c in columns]

    # Pattern 1: Classification table (explicit finish order / results table)
    # E.g. Querying race results with finish position and multiple details
    if "position" in lower_cols and len(columns) >= 6 and not any(kw in sql.lower() for kw in ["group by", "count("]):
        display_cols = [c for c in columns if c.lower() in [
            "position", "driver_name", "driver_code", "surname", "constructor", "grid", "points", "status", "finish_time"
        ]]
        if not display_cols:
            display_cols = columns[:7]

        headers = [c.replace("_", " ").title() for c in display_cols]
        rows = [[row.get(c) for c in display_cols] for row in data[:20]]
        return build_classification_table(title, headers, rows)

    # Pattern 2: Time-series / Trend over Years (Year + numeric metric)
    year_col = next((c for c in columns if c.lower() == "year" or "season" in c.lower()), None)
    if year_col:
        metric_col = pick_ranking_metric_column(sql, columns, data)
        if metric_col and metric_col != year_col:
            x_vals = [row.get(year_col) for row in data]
            y_vals = [row.get(metric_col) for row in data]
            return build_line_chart(
                title=title,
                x=x_vals,
                y=y_vals,
                x_title="Season Year",
                y_title=metric_col.replace("_", " ").title(),
                name=metric_col.replace("_", " ").title(),
            )

    # Pattern 3: Driver / Team / Circuit Leaderboard & Rankings (Horizontal Bar Chart)
    label_col = pick_category_label_column(columns, data)
    metric_col = pick_ranking_metric_column(sql, columns, data)

    if label_col and metric_col:
        # Cap to top 12–15 entries
        top_data = data[:15]
        clean_categories = [get_clean_label(row, label_col, idx) for idx, row in enumerate(top_data)]
        metric_values = [row.get(metric_col) for row in top_data]

        return build_horizontal_ranking_bar_chart(
            title=title,
            categories=clean_categories,
            values=metric_values,
            metric_name=metric_col,
            row_data=top_data,
        )

    # Fallback to Table for any result with <= 8 columns
    if len(columns) <= 8:
        headers = [c.replace("_", " ").title() for c in columns]
        rows = [[row.get(c) for c in columns] for row in data[:20]]
        return build_classification_table(title, headers, rows)

    return None
