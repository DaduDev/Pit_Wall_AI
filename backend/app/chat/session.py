"""
Conversation session management for PitWall AI.
Maintains in-memory conversation state with rolling summary and verbatim turns.
Supports context pruning (last 2 turns for local Ollama, last 4-6 turns for Gemini).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class TurnMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LastQueryEntities(BaseModel):
    """Structured context tracking entities from recent turns."""
    year: Optional[int] = None
    grand_prix: Optional[str] = None
    circuit_key: Optional[str] = None
    drivers: List[str] = Field(default_factory=list)
    corner: Optional[str] = None
    session_type: Optional[str] = "Q"
    tool: Optional[str] = None  # "telemetry" or "historical_sql"


class ConversationSession:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.rolling_summary: str = ""
        self.turns: List[TurnMessage] = []
        self.last_entities: LastQueryEntities = LastQueryEntities()
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

    def update_entities(
        self,
        year: Optional[int] = None,
        grand_prix: Optional[str] = None,
        circuit_key: Optional[str] = None,
        drivers: Optional[List[str]] = None,
        corner: Optional[str] = None,
        session_type: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> None:
        """Updates active conversation entities for multi-turn context retention."""
        if year is not None:
            self.last_entities.year = year
        if grand_prix is not None:
            self.last_entities.grand_prix = grand_prix
        if circuit_key is not None:
            self.last_entities.circuit_key = circuit_key
        if drivers is not None and len(drivers) > 0:
            self.last_entities.drivers = drivers
        if corner is not None:
            self.last_entities.corner = corner
        if session_type is not None:
            self.last_entities.session_type = session_type
        if tool is not None:
            self.last_entities.tool = tool

    def add_user_message(self, content: str) -> None:
        self.turns.append(TurnMessage(role="user", content=content))
        self.updated_at = datetime.now(timezone.utc)
        self._prune_and_summarize()

    def add_assistant_message(self, content: str) -> None:
        self.turns.append(TurnMessage(role="assistant", content=content))
        self.updated_at = datetime.now(timezone.utc)
        self._prune_and_summarize()

    def _prune_and_summarize(self) -> None:
        """
        Keeps last 6 messages verbatim. Older messages are summarized
        into the rolling summary.
        """
        MAX_VERBATIM = 6
        if len(self.turns) > MAX_VERBATIM:
            overflow_turns = self.turns[:-MAX_VERBATIM]
            summary_parts = []
            for t in overflow_turns:
                prefix = "User" if t.role == "user" else "Engineer"
                summary_parts.append(f"{prefix}: {t.content[:120]}...")
            
            overflow_summary = " | ".join(summary_parts)
            if self.rolling_summary:
                self.rolling_summary += " | " + overflow_summary
            else:
                self.rolling_summary = overflow_summary
            
            # Keep only the last MAX_VERBATIM turns
            self.turns = self.turns[-MAX_VERBATIM:]

    def get_context(self, provider: str = "gemini") -> Dict[str, Any]:
        """
        Returns contextual history formatted for LLM invocation.
        For Ollama: Prunes context to the last 2 turns to respect 8GB RAM budget.
        For Gemini: Provides rolling summary + last 4-6 verbatim turns.
        """
        if provider.lower() == "ollama":
            # Last 2 messages only
            selected_turns = self.turns[-2:]
            return {
                "rolling_summary": "",
                "messages": [{"role": t.role, "content": t.content} for t in selected_turns],
                "last_entities": self.last_entities.model_dump(),
            }
        else:
            return {
                "rolling_summary": self.rolling_summary,
                "messages": [{"role": t.role, "content": t.content} for t in self.turns],
                "last_entities": self.last_entities.model_dump(),
            }


class SessionManager:
    """In-memory thread-safe session storage."""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: Optional[str] = None, user_id: str = "anonymous") -> ConversationSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        new_id = session_id or f"ses_{uuid.uuid4().hex[:12]}"
        session = ConversationSession(session_id=new_id, user_id=user_id)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Optional[ConversationSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Singleton session manager
session_manager = SessionManager()
