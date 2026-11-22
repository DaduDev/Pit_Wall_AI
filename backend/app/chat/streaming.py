"""
Server-Sent Events (SSE) formatting helpers for PitWall AI.
Formats typed events strictly compliant with contracts/api-contracts.md.
"""

import json
from typing import Any, Dict, Optional


def sse_message(event_type: str, data: Dict[str, Any]) -> str:
    """Formats a Server-Sent Event frame."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def format_session_event(session_id: str) -> str:
    """Emitted immediately upon SSE connection establishment."""
    return sse_message("session", {"session_id": session_id})


def format_status_event(step: str, detail: str) -> str:
    """Emitted during agent reasoning and tool execution stages."""
    return sse_message("status", {"step": step, "detail": detail})


def format_text_event(delta: str) -> str:
    """Emitted as the LLM streams its natural-language commentary."""
    return sse_message("text", {"delta": delta})


def format_chart_event(chart_type: str, spec: Dict[str, Any], caption: str = "") -> str:
    """Emitted once a Plotly JSON specification is generated."""
    return sse_message(
        "chart",
        {
            "chart_type": chart_type,
            "spec": spec,
            "caption": caption,
        },
    )


def format_trace_event(
    data_domain: str,
    query: Optional[str] = None,
    execution_time_ms: Optional[float] = None,
    row_count: Optional[int] = None,
    telemetry_params: Optional[Dict[str, Any]] = None,
    interpolated_points: Optional[int] = None,
    confidence: float = 1.0,
    notes: Optional[str] = None,
) -> str:
    """Emitted with full provenance data for the collapsible Engineering Trace drawer."""
    payload: Dict[str, Any] = {
        "data_domain": data_domain,
        "confidence": confidence,
    }
    if query is not None:
        payload["query"] = query
    if execution_time_ms is not None:
        payload["execution_time_ms"] = execution_time_ms
    if row_count is not None:
        payload["row_count"] = row_count
    if telemetry_params is not None:
        payload["telemetry_params"] = telemetry_params
    if interpolated_points is not None:
        payload["interpolated_points"] = interpolated_points
    if notes is not None:
        payload["notes"] = notes

    return sse_message("trace", payload)


def format_error_event(code: str, message: str, retryable: bool = False) -> str:
    """Emitted if query execution or telemetry processing encounters an error."""
    return sse_message(
        "error",
        {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    )


def format_done_event(total_duration_ms: int) -> str:
    """Emitted as the final event of the streaming response."""
    return sse_message("done", {"total_duration_ms": total_duration_ms})
