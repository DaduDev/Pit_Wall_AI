"""
Integration tests for POST /api/chat/stream SSE streaming endpoint.
Validates:
- Successful 200 StreamingResponse.
- Emission of session, status, trace, chart, text, and done SSE frames.
- Proper grounding against DuckDB database and FastF1 telemetry corner comparison.
"""

from fastapi.testclient import TestClient
from backend.app.main import app


def test_chat_stream_historical_query():
    """Tests full streaming cycle for historical Q&A query."""
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            json={"message": "Who won the 2023 Bahrain Grand Prix?"},
        )
        assert response.status_code == 200
        text = response.text

        # Verify event sequence
        assert "event: session\n" in text
        assert "event: status\n" in text
        assert "event: trace\n" in text
        assert "event: text\n" in text
        assert "event: done\n" in text

        # Verify zero hallucination content
        assert "Verstappen" in text or "VER" in text
        assert "Red Bull" in text or "v_race_results" in text


def test_chat_stream_with_chart_generation():
    """Tests query that automatically generates and streams a Plotly chart."""
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            json={"message": "Show me Lewis Hamilton podium finishes per season"},
        )
        assert response.status_code == 200
        text = response.text

        assert "event: chart\n" in text
        assert "event: trace\n" in text
        assert "podium" in text.lower() or "ham" in text.lower()


def test_chat_stream_corner_comparison():
    """Tests query comparing two drivers through a corner with multi-panel chart & mini-map."""
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            json={"message": "Compare Verstappen and Norris through Copse at 2024 British GP Qualifying"},
        )
        assert response.status_code == 200
        text = response.text

        assert "event: session\n" in text
        assert "event: status\n" in text
        assert "event: trace\n" in text
        assert "event: chart\n" in text
        assert "event: text\n" in text
        assert "event: done\n" in text

        # Verify telemetry parameters in trace
        assert "telemetry" in text
        assert "Copse" in text or "Turn 9" in text
        assert "VER" in text and "NOR" in text
