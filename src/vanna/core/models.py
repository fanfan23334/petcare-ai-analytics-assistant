"""Compatibility shim: legacy ``vanna.core.models`` imports."""

from vanna.core import (
    LlmMessage,
    LlmRequest,
    LlmResponse,
    LlmStreamChunk,
    Message,
    ToolCall,
    ToolSchema,
    User,
)

__all__ = [
    "LlmMessage",
    "LlmRequest",
    "LlmResponse",
    "LlmStreamChunk",
    "Message",
    "ToolCall",
    "ToolSchema",
    "User",
]
