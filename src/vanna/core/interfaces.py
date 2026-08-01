"""Compatibility shim for legacy imports.

Vanna 2.0 refactored the interfaces into domain modules
(``vanna.core.agent``, ``vanna.core.llm``, ``vanna.core.system_prompt``).
A few example modules still import from ``vanna.core.interfaces``.
"""

from .agent import Agent
from .llm import LlmService
from .system_prompt import SystemPromptBuilder

__all__ = ["Agent", "LlmService", "SystemPromptBuilder"]
