"""
Unit & integration tests for $0 cloud deployment hardening:
- Settings (CORS_ORIGINS, CACHE_DIR, APP_ENV=production disabling Ollama fallback)
- GET /health endpoint schema & HTTP 200
- ArtifactStore 30-min default TTL and 200-item max-cap eviction
- QueryResponseCache repeat-hit serving with 0 LLM / A2A calls + LRU eviction
- Per-IP sliding-window rate limiter on POST /api/chat/stream returning HTTP 429
- POST /api/chat/stream SSE anti-buffering headers (X-Accel-Buffering: no)
- FastF1 Semaphore(2) and seeded vs runtime research cache separation
"""

import asyncio
import json
from fastapi.testclient import TestClient

from backend.app.a2a.artifact_store import (
    ArtifactStore,
    DEFAULT_MAX_ITEMS,
    DEFAULT_TTL_SECONDS,
)
from backend.app.a2a.agents.research_agent import ResearchAgent
from backend.app.agent.orchestrator import RaceEngineerOrchestrator
from backend.app.cache.query_cache import QueryResponseCache, get_query_cache, normalize_query_key
from backend.app.chat.session import ConversationSession
from backend.app.chat.streaming import (
    format_chart_event,
    format_done_event,
    format_text_event,
    format_trace_event,
)
from backend.app.config import Settings
from backend.app.data.fastf1_cache import FASTF1_LOAD_ASYNC_SEMAPHORE
import backend.app.llm.failover_client as fc
from backend.app.main import app


def test_production_settings_defaults_and_cors():
    """Verify APP_ENV=production disables Ollama fallback, sets CACHE_DIR=/tmp/pitwall_cache, and parses CORS_ORIGINS."""
    prod = Settings(
        _env_file=None,
        APP_ENV="production",
        CORS_ORIGINS="https://pitwall.vercel.app, https://pitwall.pages.dev",
    )
    assert prod.ENABLE_OLLAMA_FALLBACK is False
    assert prod.CACHE_DIR == "/tmp/pitwall_cache"
    assert prod.get_cors_origins() == [
        "https://pitwall.vercel.app",
        "https://pitwall.pages.dev",
    ]
    assert prod.get_fastf1_cache_dir().as_posix().endswith("/tmp/pitwall_cache/fastf1")
    assert prod.get_research_runtime_cache_dir().as_posix().endswith("/tmp/pitwall_cache/research_cache")

    local = Settings(_env_file=None, APP_ENV="local")
    assert local.ENABLE_OLLAMA_FALLBACK is True
    assert local.CACHE_DIR == "./data"


def test_app_env_production_disables_ollama_failover(monkeypatch):
    """When APP_ENV=production and cloud providers fail, failover_client skips 127.0.0.1:11434."""
    fc.reset_provider_cooldown()
    monkeypatch.setenv("APP_ENV", "production")
    assert fc.is_ollama_fallback_enabled() is False

    monkeypatch.setattr(
        fc,
        "_call_gemini_sync",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED")),
    )
    ollama_probed = {"called": False}

    def _fail_if_called(*a, **k):
        ollama_probed["called"] = True
        return fc.LLMResult(text="should not run", provider="ollama_fallback")

    monkeypatch.setattr(fc, "_call_ollama_sync", _fail_if_called)

    res = fc.generate_with_failover("Who won Monza 2024?")
    assert ollama_probed["called"] is False
    assert res.text == ""


def test_artifact_store_ttl_and_max_cap_eviction(tmp_path, monkeypatch):
    """ArtifactStore defaults to 30m TTL / 200 max items and evicts expired & oldest items beyond cap."""
    assert DEFAULT_TTL_SECONDS == 1800
    assert DEFAULT_MAX_ITEMS == 200

    now_clock = {"t": 1000.0}
    monkeypatch.setattr("backend.app.a2a.artifact_store.time.time", lambda: now_clock["t"])

    # 1. TTL eviction check
    ttl_store = ArtifactStore(storage_dir=tmp_path / "ttl", max_items=10, default_ttl_seconds=60)
    ds_exp = ttl_store.put({"row": 1})
    assert ttl_store.get(ds_exp) is not None

    now_clock["t"] = 1070.0  # past 60s TTL
    assert ttl_store.get(ds_exp) is None
    assert ttl_store.count() == 0

    # 2. Max-size cap eviction check (oldest evicted first)
    cap_store = ArtifactStore(storage_dir=tmp_path / "cap", max_items=3, default_ttl_seconds=1800)
    ids = []
    for i in range(5):
        now_clock["t"] += 1.0
        ids.append(cap_store.put({"idx": i}))

    assert cap_store.count() <= 3
    assert cap_store.get(ids[0]) is None
    assert cap_store.get(ids[1]) is None
    assert cap_store.get(ids[4])["data"]["idx"] == 4


def test_query_response_cache_repeat_hits_zero_llm(monkeypatch):
    """Repeat standalone queries hit QueryResponseCache with 0 LLM/A2A calls; LRU caps size cleanly."""
    # LRU max_items eviction check
    lru = QueryResponseCache(max_items=2, ttl_seconds=600, redis_url="")
    lru.set("k1", {"text": "1"})
    lru.set("k2", {"text": "2"})
    assert lru.get("k1")["text"] == "1"  # promotes k1 as most recent
    lru.set("k3", {"text": "3"})        # evicts k2 (least recent)
    assert lru.get("k2") is None
    assert lru.get("k1")["text"] == "1"
    assert lru.get("k3")["text"] == "3"

    # Follow-up key gating check
    assert normalize_query_key("Now show his teammate lap", has_prior_turns=True) is None
    assert normalize_query_key("  Who won   2023 Bahrain GP? ") == normalize_query_key("who won 2023 bahrain gp?")

    # Orchestrator end-to-end cache hit test (0 extra LLM/A2A runs on repeat query)
    get_query_cache().clear()
    orch = RaceEngineerOrchestrator()
    exec_calls = {"count": 0}

    async def _fake_uncached(user_message, session):
        exec_calls["count"] += 1
        yield format_trace_event(
            data_domain="historical",
            provider="gemini",
            query="SELECT 1",
            confidence=1.0,
        )
        yield format_chart_event(
            chart_type="kpi_card",
            viz_type="kpi_card",
            title="2023 Bahrain GP",
            spec={"viz_type": "kpi_card", "kpi_card": {"metrics": [{"label": "Winner", "value": "Verstappen"}]}},
            kpi_card={"metrics": [{"label": "Winner", "value": "Verstappen"}]},
        )
        yield format_text_event("Max Verstappen won the 2023 Bahrain Grand Prix.")
        yield format_done_event(42)

    monkeypatch.setattr(orch, "_execute_stream_query", _fake_uncached)

    async def _run_query(msg: str, session: ConversationSession):
        frames = []
        async for f in orch.stream_query(msg, session):
            frames.append(f)
        return frames

    s1 = ConversationSession("s1", "user1")
    frames1 = asyncio.run(_run_query("Who won the 2023 Bahrain Grand Prix?", s1))
    assert exec_calls["count"] == 1
    assert any("event: chart" in f for f in frames1)

    # New independent session + whitespace/case variant -> immediate cache hit, 0 LLM/A2A calls
    s2 = ConversationSession("s2", "user1")
    frames2 = asyncio.run(_run_query("  who won   the 2023 bahrain grand prix? ", s2))
    assert exec_calls["count"] == 1, "Repeat standalone query MUST hit cache without invoking A2A/LLM!"
    trace_frames = [json.loads(f.split("data: ", 1)[1]) for f in frames2 if f.startswith("event: trace")]
    assert trace_frames and trace_frames[0]["provider"] == "cache"
    assert any("event: chart" in f for f in frames2)


def test_chat_stream_sse_headers_and_per_ip_rate_limit(monkeypatch, auth_header):
    """POST /api/chat/stream sets X-Accel-Buffering: no and enforces per-IP sliding-window HTTP 429."""
    from backend.app.chat import router as chat_router

    chat_router.rate_limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "3")

    async def _fast_stream(user_message, session):
        yield format_text_event("Copy that, checking data.")
        yield format_done_event(5)

    monkeypatch.setattr(chat_router.orchestrator, "stream_query", _fast_stream)

    with TestClient(app) as client:
        # Verify /health endpoint returns HTTP 200 with required deployment diagnostics
        h_resp = client.get("/health")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["status"] == "ok"
        assert "env" in h_data
        assert isinstance(h_data["duckdb_ready"], bool)
        assert "fastf1_cache_dir" in h_data
        assert isinstance(h_data["active_providers"], list)

        # Requests 1..3 from IP A succeed with SSE anti-buffering headers
        headers_ip_a = {**auth_header, "X-Forwarded-For": "198.51.100.10"}
        for _ in range(3):
            resp = client.post(
                "/api/chat/stream",
                json={"message": "Test SSE"},
                headers=headers_ip_a,
            )
            assert resp.status_code == 200
            assert resp.headers.get("cache-control") == "no-cache"
            assert resp.headers.get("x-accel-buffering") == "no"

        # Request 4 from IP A hits sliding-window rate limit -> HTTP 429
        blocked = client.post(
            "/api/chat/stream",
            json={"message": "Exceeds limit"},
            headers=headers_ip_a,
        )
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["code"] == "RATE_LIMIT_EXHAUSTED"
        assert "PitWall Radio" in body["detail"]

        # Request from IP B still succeeds independently
        allowed_b = client.post(
            "/api/chat/stream",
            json={"message": "Other IP"},
            headers={**auth_header, "X-Forwarded-For": "198.51.100.25"},
        )
        assert allowed_b.status_code == 200

    chat_router.rate_limiter.reset()


def test_protected_routes_enforce_auth_and_public_health_stays_open(auth_header):
    """
    Verify public health/status routes succeed without credentials while all chat, telemetry,
    historical, research, viz, and profile routes reject missing, invalid, or expired tokens (401).
    """
    from backend.tests.conftest import make_test_supabase_jwt

    expired_header = {"Authorization": f"Bearer {make_test_supabase_jwt(exp_offset_seconds=-120)}"}
    invalid_header = {"Authorization": "Bearer malformed.jwt.token"}

    protected_posts = [
        ("/api/chat/stream", {"message": "Who won Bahrain 2023?"}),
        ("/a2a/historical/query", {"question": "Who won Bahrain 2023?"}),
        ("/a2a/telemetry/compare-corners", {"year": 2024, "grand_prix": "Silverstone", "driver_1": "VER", "driver_2": "NOR", "corner": "Copse"}),
        ("/a2a/telemetry/compare-lap", {"year": 2024, "grand_prix": "Montreal", "driver_1": "RUS", "driver_2": "VER"}),
        ("/a2a/telemetry/tyre-stints", {"year": 2024, "grand_prix": "Monza", "drivers": ["LEC"]}),
        ("/a2a/research/query", {"query": "2026 F1 engine rules"}),
        ("/a2a/viz/render", {"dataset_id": "nonexistent", "domain": "historical_sql"}),
    ]

    with TestClient(app) as client:
        # Public monitoring & discovery routes remain open without credentials
        for public_path in ("/", "/health", "/api/health", "/a2a/historical/.well-known/agent-card.json"):
            pub_res = client.get(public_path)
            assert pub_res.status_code == 200, f"Public endpoint {public_path} returned {pub_res.status_code}"

        # /api/auth/me enforces missing, invalid, expired, and accepts valid
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me", headers=invalid_header).status_code == 401
        assert client.get("/api/auth/me", headers=expired_header).status_code == 401
        assert client.get("/api/auth/me", headers=auth_header).status_code == 200

        # Protected chat & A2A routes reject missing, invalid, and expired tokens with 401
        for path, payload in protected_posts:
            assert client.post(path, json=payload).status_code == 401, f"{path} must reject missing token"
            assert client.post(path, json=payload, headers=invalid_header).status_code == 401, f"{path} must reject invalid token"
            assert client.post(path, json=payload, headers=expired_header).status_code == 401, f"{path} must reject expired token"


def test_fastf1_semaphore_and_seeded_research_cache(tmp_path, monkeypatch):
    """Verify FastF1 Semaphore(2) bound and ResearchAgent reading seeded cache while writing to runtime CACHE_DIR."""
    assert FASTF1_LOAD_ASYNC_SEMAPHORE._value == 2

    seed_dir = tmp_path / "seed_research"
    runtime_dir = tmp_path / "tmp_runtime" / "research_cache"
    seed_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)

    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "tmp_runtime"))
    agent = ResearchAgent(cache_dir=None)
    agent.seed_cache_dir = seed_dir
    agent.cache_dir = runtime_dir
    agent._explicit_cache_dir = False

    # Place seeded grounded response in seed_dir (like Docker COPY ./data/research_cache/)
    seed_payload = {
        "query": "2026 F1 active aero",
        "summary": "2026 cars feature X-mode and Z-mode active aerodynamics.",
        "findings": ["Movable front and rear wing elements."],
        "sources": [{"title": "FIA", "url": "https://www.fia.com"}],
        "grounded": True,
    }
    seed_path = agent._cache_path_for_query("2026 F1 active aero", seed_dir)
    seed_path.write_text(json.dumps(seed_payload), encoding="utf-8")

    res = agent.research_topic("2026 F1 active aero")
    assert res["provider"] == "cache"
    assert res["grounded"] is True
    assert "active aerodynamics" in res["summary"]
