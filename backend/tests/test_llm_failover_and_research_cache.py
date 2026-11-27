"""
Unit tests verifying:
1. Gemini 429 RESOURCE_EXHAUSTED triggers automatic runtime failover to local Ollama (qwen3.5:4b)
   for ResearchAgent, HistoricalSQLAgent, and PitWallEngineer without leaking raw error JSON.
2. Empty/whitespace '-' bullets are stripped cleanly before rendering WebIntelligenceCard.
3. Second identical research query hits ./data/research_cache/ with 0 live Gemini API calls
   and emits provider='cache' in trace.
"""

import asyncio
import json
import httpx
import pytest

import backend.app.llm.failover_client as fc
from backend.app.a2a.agents.research_agent import ResearchAgent
from backend.app.a2a.agents.historical_agent import HistoricalSQLAgent
from backend.app.a2a.agents.presentation_agent import get_presentation_agent


def test_gemini_429_failover_to_ollama_and_clean_bullets(tmp_path, monkeypatch):
    """
    On 429 RESOURCE_EXHAUSTED from Gemini google_search, ResearchAgent MUST automatically
    fail over to local Ollama, set grounded=False & provider='ollama_fallback',
    strip blank '- ' bullets, and never leak raw 429 JSON into summary/bullets.
    """
    def _raise_429(*args, **kwargs):
        raise RuntimeError(
            '429 RESOURCE_EXHAUSTED: {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}'
        )

    ollama_calls = {"count": 0}

    def _mock_ollama(prompt, *, system_instruction=None, timeout=20.0):
        ollama_calls["count"] += 1
        return fc.LLMResult(
            text=(
                "Max Verstappen and Lewis Hamilton went wide at Turn 4 on Lap 48 during the 2021 Brazilian GP.\n"
                "-\n"
                "-   \n"
                "- Both cars ran off track at Turn 4 exit without contact\n"
                "- Stewards ruled no investigation necessary during the Grand Prix\n"
                "* "
            ),
            provider="ollama_fallback",
            grounded=False,
            sources=[],
            model_used="qwen3.5:4b",
        )

    monkeypatch.setattr(fc, "_call_gemini_sync", _raise_429)
    monkeypatch.setattr(fc, "_call_ollama_sync", _mock_ollama)

    agent = ResearchAgent(cache_dir=tmp_path)
    res = agent.research_topic("What happened at Turn 4 in Brazil 2021?")

    assert ollama_calls["count"] == 1
    assert res["success"] is True
    assert res["grounded"] is False
    assert res["provider"] == "ollama_fallback"
    assert res["trace"]["provider"] == "ollama_fallback"
    assert res["sources"] == []
    assert "RESOURCE_EXHAUSTED" not in res["summary"]
    assert "429" not in res["summary"]

    findings = res["web_card"]["key_findings"]
    assert len(findings) == 2
    assert all(b.strip() for b in findings)
    assert "-" not in findings
    assert all("RESOURCE_EXHAUSTED" not in b for b in findings)

    # Render through PresentationAgent and verify clean bullets + grounded=False
    pa = get_presentation_agent()
    viz = pa.render_visualization(dataset_id=res["dataset_id"], domain="research")
    assert viz["viz_type"] == "web_intelligence_card"
    card = viz["web_intelligence_card"]
    assert card["grounded"] is False
    assert card["provider"] == "ollama_fallback"
    assert len(card["bullets"]) == 2
    assert all(b.strip() for b in card["bullets"])


def test_research_cache_hits_on_second_identical_query(tmp_path, monkeypatch):
    """
    First research query calls Gemini + google_search and persists to cache_dir;
    second identical (case/whitespace normalized) query hits disk cache with 0 API calls.
    """
    api_calls = {"count": 0}

    def _mock_grounded_gemini(*args, **kwargs):
        api_calls["count"] += 1
        return fc.LLMResult(
            text=(
                "The 2026 Formula 1 power unit regulations introduce a 50/50 ICE and electrical split.\n"
                "- MGU-H is removed to simplify power unit architecture.\n"
                "- Electrical MGU-K output increases to 350kW.\n"
                "- Cars run on 100% sustainable synthetic fuel."
            ),
            provider="gemini",
            grounded=True,
            sources=[{"title": "FIA 2026 Technical Regulations", "url": "https://www.fia.com/regulations", "uri": "https://www.fia.com/regulations"}],
            model_used="gemini-3.5-flash-lite",
        )

    monkeypatch.setattr(fc, "_call_gemini_sync", _mock_grounded_gemini)

    agent = ResearchAgent(cache_dir=tmp_path)
    res1 = agent.research_topic("What are the 2026 F1 engine rules?")
    assert api_calls["count"] == 1
    assert res1["provider"] == "gemini"
    assert res1["trace"]["provider"] == "gemini"
    assert res1["grounded"] is True
    assert len(res1["sources"]) == 1

    # Second identical query with extra whitespace & casing variations
    res2 = agent.research_topic("  what are the 2026 F1   engine rules? ")
    assert api_calls["count"] == 1, "Second query must hit disk cache with 0 Gemini API calls!"
    assert res2["provider"] == "cache"
    assert res2["trace"]["provider"] == "cache"
    assert res2["grounded"] is True
    assert res2["sources"] == res1["sources"]


def test_historical_sql_gemini_429_failover_to_ollama(monkeypatch):
    """HistoricalSQLAgent SQL generation fails over to local Ollama on Gemini 429 and sets trace.provider."""
    def _raise_429(*args, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    def _mock_ollama_sql(prompt, *, system_instruction=None, timeout=15.0):
        return fc.LLMResult(
            text="SELECT year, grand_prix, driver_name, constructor, position FROM v_race_results WHERE year = 2021 AND lower(grand_prix) LIKE '%brazil%' AND position = 1 LIMIT 1",
            provider="ollama_fallback",
            grounded=False,
            sources=[],
            model_used="qwen3.5:4b",
        )

    monkeypatch.setattr(fc, "_call_gemini_sync", _raise_429)
    monkeypatch.setattr(fc, "_call_ollama_sync", _mock_ollama_sql)

    agent = HistoricalSQLAgent()
    res = agent.query("Who won the 2021 Brazilian Grand Prix?")

    assert res["success"] is True
    assert res["provider"] == "ollama_fallback"
    assert res["trace"]["provider"] == "ollama_fallback"
    assert res["row_count"] == 1
    assert "RESOURCE_EXHAUSTED" not in res["summary"]
    assert res["sample_rows"][0]["driver_name"] == "Lewis Hamilton"


def test_stream_with_failover_429_to_ollama_ndjson(monkeypatch):
    """Async commentary stream seamlessly fails over to local Ollama NDJSON stream on Gemini 429."""
    class _FailingClient:
        class aio:
            class models:
                @staticmethod
                async def generate_content_stream(*args, **kwargs):
                    raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(fc, "_get_genai_client", lambda cfg: _FailingClient())

    class _FakeOllamaStreamResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "Copy that, "}})
            yield json.dumps({"message": {"content": "Hamilton won Brazil 2021."}})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    captured_stream = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured_stream["timeout"] = kwargs.get("timeout")

        def stream(self, method, url, **kwargs):
            captured_stream["url"] = url
            captured_stream["json"] = kwargs.get("json")
            return _FakeOllamaStreamResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    async def _collect():
        state = {}
        chunks = []
        async for ch in fc.stream_with_failover(
            "Summarize Brazil 2021",
            fallback_text="Deterministic fallback",
            provider_state=state,
        ):
            chunks.append(ch)
        return "".join(chunks), state

    text, state = asyncio.run(_collect())
    assert text == "Copy that, Hamilton won Brazil 2021."
    assert state["provider"] == "ollama_fallback"
    assert "429" not in text
    assert captured_stream["json"]["think"] is False
    assert captured_stream["json"]["keep_alive"] == "15m"
    assert captured_stream["json"]["options"] == {
        "num_ctx": 1024,
        "num_predict": 180,
        "temperature": 0.3,
    }
    assert isinstance(captured_stream["timeout"], httpx.Timeout)
    assert captured_stream["timeout"].read == 150.0
    assert captured_stream["timeout"].connect == 5.0


def test_ollama_sync_payload_ipv4_and_timeouts(monkeypatch):
    """Verify IPv4 127.0.0.1 default URL normalization, options, 150s sync timeout, and 180s A2A timeout."""
    from backend.app.config import Settings
    from backend.app.a2a.client import A2AClient

    default_settings = Settings(_env_file=None)
    assert default_settings.OLLAMA_API_BASE == "http://127.0.0.1:11434"
    assert default_settings.OLLAMA_BASE_URL == "http://127.0.0.1:11434/api/chat"

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/api/chat/api/chat/")
    assert fc.get_ollama_chat_url() == "http://127.0.0.1:11434/api/chat"

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    assert fc.get_ollama_chat_url() == "http://127.0.0.1:11434/api/chat"

    captured = {}

    class _FakeSyncResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "SELECT 1"}}

    def _fake_httpx_post(url, *, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeSyncResp()

    monkeypatch.setattr(httpx, "post", _fake_httpx_post)

    res = fc._call_ollama_sync("Test prompt")
    assert res.text == "SELECT 1"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["think"] is False
    assert captured["json"]["keep_alive"] == "15m"
    assert captured["json"]["options"] == {
        "num_ctx": 1024,
        "num_predict": 180,
        "temperature": 0.3,
    }
    assert isinstance(captured["timeout"], httpx.Timeout)
    assert captured["timeout"].read == 150.0
    assert captured["timeout"].connect == 5.0

    # Verify A2AClient 180s timeout
    a2a_client = A2AClient(use_asgi=True)
    http_client = a2a_client._get_http_client()
    assert http_client.timeout.read == 180.0
    asyncio.run(a2a_client.close())


def test_gemini_429_60s_cooldown_skips_redundant_calls(monkeypatch):
    """After a 429 RESOURCE_EXHAUSTED error, subsequent calls in the 60s window skip Gemini and go directly to Ollama."""
    fc.reset_gemini_cooldown()
    gemini_calls = {"count": 0}
    ollama_calls = {"count": 0}

    def _failing_gemini(*args, **kwargs):
        gemini_calls["count"] += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")

    def _ok_ollama(prompt, *, system_instruction=None, timeout=150.0):
        ollama_calls["count"] += 1
        return fc.LLMResult(
            text="Concise F1 summary.\n- Fact one\n- Fact two",
            provider="ollama_fallback",
            grounded=False,
            sources=[],
            model_used="qwen3.5:4b",
        )

    monkeypatch.setattr(fc, "_call_gemini_sync", _failing_gemini)
    monkeypatch.setattr(fc, "_call_ollama_sync", _ok_ollama)

    # First call hits Gemini -> gets 429 -> triggers 60s cooldown -> falls back to Ollama
    res1 = fc.generate_with_failover("First query")
    assert gemini_calls["count"] == 1
    assert ollama_calls["count"] == 1
    assert res1.provider == "ollama_fallback"
    assert fc.is_gemini_in_cooldown() is True
    assert fc.get_active_provider_hint() == "ollama_fallback"

    # Second call within 60s skips Gemini completely (0 extra Gemini calls)
    res2 = fc.generate_with_failover("Second query")
    assert gemini_calls["count"] == 1, "Cooldown must prevent redundant 429 Gemini calls!"
    assert ollama_calls["count"] == 2
    assert res2.provider == "ollama_fallback"
    fc.reset_gemini_cooldown()


def test_presentation_agent_strips_blank_and_prefixed_bullets():
    """Verify PresentationAgent strips leading '-', '*', '•', '1.' prefixes, embedded '- \\n- ', and drops empty bullets."""
    from backend.app.a2a.artifact_store import get_artifact_store

    store = get_artifact_store()
    ds_id = store.put(
        data={
            "summary": "FIA 2026 rules summary.\n-   \n* ",
            "findings": ["-", "-   ", "• ", "- \n- Live web grounding info", "1. 50/50 power split", "*   "],
            "sources": [],
            "grounded": False,
            "provider": "ollama_fallback",
        },
        metadata={"domain": "research", "query": "2026 rules"},
    )
    pa = get_presentation_agent()
    viz = pa.render_visualization(dataset_id=ds_id, domain="research")
    card = viz["web_intelligence_card"]
    assert card["bullets"] == ["Live web grounding info", "50/50 power split"]
    assert card["summary"] == "FIA 2026 rules summary."
