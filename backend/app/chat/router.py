"""
Chat and Streaming Router for PitWall AI.
Implements POST /api/chat/stream delivering SSE events
for historical Q&A and telemetry analysis.
"""

import time
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.app.chat.session import session_manager
from backend.app.chat.streaming import (
    format_session_event,
    format_error_event,
    format_done_event,
)
from backend.app.agent.orchestrator import RaceEngineerOrchestrator

router = APIRouter(prefix="/api/chat", tags=["Chat"])

orchestrator = RaceEngineerOrchestrator()


class ChatStreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@router.post("/stream")
async def chat_stream(body: ChatStreamRequest, request: Request):
    """
    Primary conversational endpoint streaming real-time status, text,
    Plotly charts, and engineering traces over Server-Sent Events (SSE).
    """
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
