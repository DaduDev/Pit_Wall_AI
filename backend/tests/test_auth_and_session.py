"""
Unit tests for Authentication, JWT issuance, Session Management, and Streaming Helpers.
"""

import pytest
from backend.app.auth.dependencies import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    USERS_DB,
)
from backend.app.chat.session import ConversationSession, SessionManager
from backend.app.chat.streaming import (
    format_session_event,
    format_status_event,
    format_text_event,
    format_chart_event,
    format_trace_event,
    format_error_event,
    format_done_event,
)


def test_password_hashing():
    pw = "SecretF1Pass!2024"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("WrongPassword", h)


def test_demo_user_authentication():
    demo_user = USERS_DB["demo@pitwall.ai"]
    assert verify_password("Pitwall2024!", demo_user.password_hash)


def test_jwt_token_lifecycle():
    token = create_access_token({"sub": "driver@pitwall.ai", "user_id": "usr_test"})
    payload = decode_access_token(token)
    assert payload["sub"] == "driver@pitwall.ai"
    assert payload["user_id"] == "usr_test"
    assert "exp" in payload


def test_session_management_and_pruning():
    sess = ConversationSession(session_id="test_ses_1", user_id="test_user")
    
    # Add 4 turns (8 messages)
    for i in range(8):
        if i % 2 == 0:
            sess.add_user_message(f"Query {i}")
        else:
            sess.add_assistant_message(f"Answer {i}")

    # Maximum 6 messages kept verbatim
    assert len(sess.turns) == 6
    # Rolling summary was created for older messages
    assert len(sess.rolling_summary) > 0

    # Ollama context trims to last 2 turns
    ollama_ctx = sess.get_context(provider="ollama")
    assert len(ollama_ctx["messages"]) == 2

    # Gemini context preserves up to 6 turns + rolling summary
    gemini_ctx = sess.get_context(provider="gemini")
    assert len(gemini_ctx["messages"]) == 6
    assert len(gemini_ctx["rolling_summary"]) > 0


def test_sse_streaming_formatters():
    # Session
    s_evt = format_session_event("ses_123")
    assert "event: session\n" in s_evt
    assert '"session_id": "ses_123"' in s_evt

    # Status
    st_evt = format_status_event("querying_sql", "Running DuckDB query")
    assert "event: status\n" in st_evt
    assert '"step": "querying_sql"' in st_evt

    # Text
    t_evt = format_text_event("Max Verstappen won")
    assert "event: text\n" in t_evt
    assert '"delta": "Max Verstappen won"' in t_evt

    # Chart
    c_evt = format_chart_event("bar", {"data": []}, "2023 Wins")
    assert "event: chart\n" in c_evt
    assert '"chart_type": "bar"' in c_evt

    # Trace
    tr_evt = format_trace_event(
        data_domain="historical",
        query="SELECT * FROM v_race_results",
        execution_time_ms=12.5,
        row_count=1,
    )
    assert "event: trace\n" in tr_evt
    assert '"data_domain": "historical"' in tr_evt
    assert '"execution_time_ms": 12.5' in tr_evt

    # Error
    err_evt = format_error_event("DATA_NOT_FOUND", "No race data for 1948", retryable=False)
    assert "event: error\n" in err_evt
    assert '"code": "DATA_NOT_FOUND"' in err_evt

    # Done
    d_evt = format_done_event(540)
    assert "event: done\n" in d_evt
    assert '"total_duration_ms": 540' in d_evt
