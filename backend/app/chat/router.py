"""
Chat and Streaming Router for PitWall AI.
Implements POST /api/chat/stream delivering SSE events with anti-buffering headers
and lightweight per-IP sliding-window rate limiting.
"""

from collections import deque
import os
import threading
import time
from typing import Dict, Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.chat.session import session_manager
from backend.app.chat.streaming import (
    format_session_event,
    format_error_event,
    format_done_event,
)
from backend.app.agent.orchestrator import RaceEngineerOrchestrator

router = APIRouter(prefix="/api/chat", tags=["Chat"])

orchestrator = RaceEngineerOrchestrator()


class SlidingWindowRateLimiter:
    """Thread-safe per-IP sliding-window (60s) rate limiter."""

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._hits: Dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _get_limit(self) -> int:
        raw = os.environ.get("RATE_LIMIT_PER_MIN")
        if raw is not None and raw.strip().isdigit():
            return max(1, int(raw.strip()))
        return max(1, int(getattr(settings, "RATE_LIMIT_PER_MIN", 15)))

    def check_and_record(self, client_ip: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds) for client_ip under current limit."""
        limit = self._get_limit()
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.setdefault(client_ip, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])) + 1)
                return False, retry_after
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter(window_seconds=60.0)


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class ChatStreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/stream")
async def chat_stream(body: ChatStreamRequest, request: Request):
    """
    Primary conversational endpoint streaming real-time status, text,
    Plotly charts, and engineering traces over Server-Sent Events (SSE).
    """
    client_ip = _extract_client_ip(request)
    allowed, retry_after = rate_limiter.check_and_record(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={
                "code": "RATE_LIMIT_EXHAUSTED",
                "detail": (
                    "PitWall Radio busy: request limit reached for this pit-wall terminal. "
                    f"Please stand by {retry_after}s before transmitting again."
                ),
            },
        )

    session = session_manager.get_or_create(session_id=body.session_id)

    async def event_generator():
        t_start = time.perf_counter()
        emitted_done = False
        try:
            # Emit session event first
            yield format_session_event(session.session_id)

            # Stream reasoning, tool calls, charts, traces, and commentary
            async for chunk in orchestrator.stream_query(
                user_message=body.message,
                session=session,
            ):
                if await request.is_disconnected():
                    break
                if "event: done" in chunk:
                    emitted_done = True
                yield chunk
        except Exception as e:
            yield format_error_event(
                code="STREAM_ERROR",
                message=f"Stream encountered unexpected error: {str(e)}",
                retryable=True,
            )
        finally:
            if not emitted_done:
                elapsed_ms = int((time.perf_counter() - t_start) * 1000)
                yield format_done_event(total_duration_ms=elapsed_ms)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
