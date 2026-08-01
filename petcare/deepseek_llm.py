"""DeepSeek LLM adapter (OpenAI-compatible) with dict-tool tolerance.

DeepSeek exposes an OpenAI-compatible Chat Completions + Tool Call API, so we
reuse Vanna's OpenAILlmService. One incompatibility: the Agent passes tool
schemas as plain dicts while OpenAILlmService expects ToolSchema objects.
This adapter normalizes dicts before delegating - Vanna core is NOT modified.
"""

from __future__ import annotations

from typing import Any, Dict, List

from vanna.core.llm import LlmRequest
from vanna.core.tool import ToolSchema
from vanna.integrations.openai import OpenAILlmService


class DeepSeekLlmService(OpenAILlmService):
    """OpenAI-compatible DeepSeek service tolerant of dict tool schemas."""

    def _build_payload(self, request: LlmRequest) -> Dict[str, Any]:
        tools = request.tools
        if tools and any(isinstance(t, dict) for t in tools):
            normalized: List[Any] = []
            for t in tools:
                if isinstance(t, dict):
                    normalized.append(
                        ToolSchema(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            parameters=t.get("parameters", {"type": "object", "properties": {}}),
                        )
                    )
                else:
                    normalized.append(t)
            request = request.model_copy(update={"tools": normalized})
        return super()._build_payload(request)
