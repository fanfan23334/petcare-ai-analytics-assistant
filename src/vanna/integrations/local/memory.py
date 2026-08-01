"""
In-memory implementations for agent memory and user resolution.

These provide working defaults so agents can be constructed with only
``llm_service`` and ``tool_registry`` (as shown in the README), even though
the 2.0 API refactor made ``user_resolver`` / ``agent_memory`` required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from vanna.capabilities.agent_memory import AgentMemory
from vanna.capabilities.agent_memory.models import (
    TextMemory,
    TextMemorySearchResult,
    ToolMemory,
    ToolMemorySearchResult,
)
from vanna.core.user import User
from vanna.core.user.request_context import RequestContext
from vanna.core.user.resolver import UserResolver

if TYPE_CHECKING:
    from vanna.core.tool import ToolContext


class InMemoryAgentMemory(AgentMemory):
    """Simple in-memory agent memory, sufficient for local development."""

    def __init__(self) -> None:
        self._tool_memories: List[ToolMemory] = []
        self._text_memories: List[TextMemory] = []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: Dict[str, Any],
        context: "ToolContext",
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._tool_memories.append(
            ToolMemory(
                memory_id=str(uuid.uuid4()),
                question=question,
                tool_name=tool_name,
                args=args,
                timestamp=self._now(),
                success=success,
                metadata=metadata,
            )
        )

    async def save_text_memory(
        self, content: str, context: "ToolContext"
    ) -> TextMemory:
        memory = TextMemory(
            memory_id=str(uuid.uuid4()), content=content, timestamp=self._now()
        )
        self._text_memories.append(memory)
        return memory

    async def search_similar_usage(
        self,
        question: str,
        context: "ToolContext",
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        tool_name_filter: Optional[str] = None,
    ) -> List[ToolMemorySearchResult]:
        candidates = self._tool_memories
        if tool_name_filter:
            candidates = [m for m in candidates if m.tool_name == tool_name_filter]
        results = [
            ToolMemorySearchResult(memory=memory, similarity_score=0.0, rank=i + 1)
            for i, memory in enumerate(candidates[:limit])
        ]
        return results

    async def search_text_memories(
        self,
        query: str,
        context: "ToolContext",
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[TextMemorySearchResult]:
        results = [
            TextMemorySearchResult(memory=memory, similarity_score=0.0, rank=i + 1)
            for i, memory in enumerate(self._text_memories[:limit])
        ]
        return results

    async def get_recent_memories(
        self, context: "ToolContext", limit: int = 10
    ) -> List[ToolMemory]:
        return list(reversed(self._tool_memories[-limit:]))

    async def get_recent_text_memories(
        self, context: "ToolContext", limit: int = 10
    ) -> List[TextMemory]:
        return list(reversed(self._text_memories[-limit:]))

    async def delete_by_id(self, context: "ToolContext", memory_id: str) -> bool:
        before = len(self._tool_memories)
        self._tool_memories = [m for m in self._tool_memories if m.memory_id != memory_id]
        return len(self._tool_memories) < before

    async def delete_text_memory(self, context: "ToolContext", memory_id: str) -> bool:
        before = len(self._text_memories)
        self._text_memories = [
            m for m in self._text_memories if m.memory_id != memory_id
        ]
        return len(self._text_memories) < before

    async def clear_memories(
        self,
        context: "ToolContext",
        tool_name: Optional[str] = None,
        before_date: Optional[str] = None,
    ) -> int:
        removed = 0
        if tool_name is not None:
            kept = [m for m in self._tool_memories if m.tool_name != tool_name]
            removed += len(self._tool_memories) - len(kept)
            self._tool_memories = kept
        if before_date is not None:
            kept = [
                m
                for m in self._tool_memories
                if m.timestamp is None or m.timestamp >= before_date
            ]
            removed += len(self._tool_memories) - len(kept)
            self._tool_memories = kept
        if tool_name is None and before_date is None:
            removed = len(self._tool_memories) + len(self._text_memories)
            self._tool_memories = []
            self._text_memories = []
        return removed


class AnonymousUserResolver(UserResolver):
    """Resolves every request to a single anonymous user."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="anonymous", username="anonymous")
