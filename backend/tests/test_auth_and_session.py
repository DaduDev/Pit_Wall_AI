"""
Unit tests for stateless Supabase JWT authentication (JWKS PyJWKClient + optional HS256 fallback),
ConversationSession pruning, and SSE streaming formatters.
"""

from datetime import datetime, timedelta, timezone
import json
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
import jwt
import pytest

from backend.app.auth.dependencies import (
    clear_jwk_cache,
    decode_access_token,
    get_current_user,
    user_from_claims,
)
from backend.app.chat.session import ConversationSession
from backend.app.chat.streaming import (
    format_chart_event,
    format_done_event,
    format_error_event,
    format_session_event,
    format_status_event,
    format_text_event,
    format_trace_event,
)
from backend.app.main import app
from backend.tests.conftest import TEST_SUPABASE_JWT_SECRET, TEST_SUPABASE_URL, make_test_supabase_jwt


def _generate_rsa_keypair_and_jwks(kid: str = "supabase-test-kid-1"):
    """Generate an ephemeral RS256 private key and corresponding JWKS dict for offline JWKS testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = kid
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"
    return private_key, {"keys": [public_jwk]}


def test_supabase_jwks_verification_cached_and_off_event_loop(monkeypatch):
    """Verify RS256 Bearer JWTs against cached PyJWKClient with audience='authenticated'."""
    clear_jwk_cache()
    private_key, jwks_payload = _generate_rsa_keypair_and_jwks()

    fetch_calls = {"count": 0}
    orig_fetch = jwt.PyJWKClient.fetch_data

    def _mock_fetch_data(self):
        fetch_calls["count"] += 1
        assert self.uri == f"{TEST_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        return jwks_payload

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _mock_fetch_data)
    monkeypatch.setenv("SUPABASE_URL", TEST_SUPABASE_URL)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "usr_sb_rs256",
            "email": "charles@pitwall.test",
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{TEST_SUPABASE_URL}/auth/v1",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "user_metadata": {"display_name": "Charles Leclerc"},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "supabase-test-kid-1"},
    )

    payload = decode_access_token(token)
    assert payload["sub"] == "usr_sb_rs256"
    assert payload["aud"] == "authenticated"
    assert fetch_calls["count"] == 1

    # Second call reuses cached PyJWKClient & cached JWK without another network fetch
    import asyncio
    user = asyncio.run(
        get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
    )
    assert user.id == "usr_sb_rs256"
    assert user.email == "charles@pitwall.test"
    assert user.display_name == "Charles Leclerc"
    assert fetch_calls["count"] == 1
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", orig_fetch)


def test_supabase_hs256_fallback_and_rejection_cases(monkeypatch):
    """Cover valid HS256 fallback, unset secret rejection, expired, wrong audience, invalid signature, and missing creds."""
    valid_hs = make_test_supabase_jwt(sub="usr_hs_1", email="oscar@pitwall.test")
    claims = decode_access_token(valid_hs)
    user = user_from_claims(claims)
    assert user.id == "usr_hs_1"
    assert user.email == "oscar@pitwall.test"

    # Expired token -> HTTP 401
    expired = make_test_supabase_jwt(exp_offset_seconds=-60)
    with pytest.raises(HTTPException) as exc_exp:
        decode_access_token(expired)
    assert exc_exp.value.status_code == 401
    assert "expired" in exc_exp.value.detail.lower()

    # Wrong audience -> HTTP 401
    wrong_aud = make_test_supabase_jwt(aud="anon")
    with pytest.raises(HTTPException) as exc_aud:
        decode_access_token(wrong_aud)
    assert exc_aud.value.status_code == 401
    assert "audience" in exc_aud.value.detail.lower()

    # Wrong signature / malformed -> HTTP 401
    bad_sig = make_test_supabase_jwt(secret="completely-different-wrong-secret-32chars")
    with pytest.raises(HTTPException) as exc_bad:
        decode_access_token(bad_sig)
    assert exc_bad.value.status_code == 401

    with pytest.raises(HTTPException) as exc_malformed:
        decode_access_token("not.a.valid.jwt")
    assert exc_malformed.value.status_code == 401

    # Missing secret rejects HS256 legacy token cleanly -> HTTP 401
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc_no_secret:
        decode_access_token(valid_hs)
    assert exc_no_secret.value.status_code == 401


def test_auth_me_endpoint_valid_and_missing_token(auth_header):
    """Verify GET /api/auth/me returns stateless claims on valid token and 401 without Bearer credentials."""
    with TestClient(app) as client:
        missing = client.get("/api/auth/me")
        assert missing.status_code == 401

        invalid = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})
        assert invalid.status_code == 401

        ok = client.get("/api/auth/me", headers=auth_header)
        assert ok.status_code == 200
        data = ok.json()
        assert data["id"] == "usr_test_001"
        assert data["email"] == "engineer@pitwall.test"
        assert data["display_name"] == "Test Engineer"


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
    s_evt = format_session_event("ses_123")
    assert "event: session\n" in s_evt
    assert '"session_id": "ses_123"' in s_evt

    st_evt = format_status_event("querying_sql", "Running DuckDB query")
    assert "event: status\n" in st_evt
    assert '"step": "querying_sql"' in st_evt

    t_evt = format_text_event("Max Verstappen won")
    assert "event: text\n" in t_evt
    assert '"delta": "Max Verstappen won"' in t_evt

    c_evt = format_chart_event("bar", {"data": []}, "2023 Wins")
    assert "event: chart\n" in c_evt
    assert '"chart_type": "bar"' in c_evt

    tr_evt = format_trace_event(
        data_domain="historical",
        query="SELECT * FROM v_race_results",
        execution_time_ms=12.5,
        row_count=1,
    )
    assert "event: trace\n" in tr_evt
    assert '"data_domain": "historical"' in tr_evt
    assert '"execution_time_ms": 12.5' in tr_evt

    err_evt = format_error_event("DATA_NOT_FOUND", "No race data for 1948", retryable=False)
    assert "event: error\n" in err_evt
    assert '"code": "DATA_NOT_FOUND"' in err_evt

    d_evt = format_done_event(540)
    assert "event: done\n" in d_evt
    assert '"total_duration_ms": 540' in d_evt
