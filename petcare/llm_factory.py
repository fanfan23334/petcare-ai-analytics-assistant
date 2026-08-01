"""LLM provider factory for PetCare.

Reads LLM_PROVIDER from config:
- mock     -> PetCareMockLlmService (deterministic, no API key, default)
- deepseek -> Vanna's OpenAILlmService pointed at DeepSeek's
              OpenAI-compatible endpoint (base_url). No Vanna core changes.

Never logs or returns the API key. Missing key raises a clear error.
"""

from __future__ import annotations

from vanna.core.llm import LlmService

from .config import PetCareConfig
from .deepseek_llm import DeepSeekLlmService
from .mock_llm import PetCareMockLlmService

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


def create_llm_service(config: PetCareConfig) -> LlmService:
    """Build the LLM service for the configured provider (never returns secrets)."""
    provider = (config.llm_provider or "mock").lower().strip()

    if provider == "mock":
        return PetCareMockLlmService(as_of_date=config.as_of_date)

    if provider == "deepseek":
        if not config.llm_api_key:
            raise ValueError(
                "LLM_PROVIDER=deepseek 需要配置 LLM_API_KEY（设置环境变量或 petcare/.env）"
            )
        model = config.llm_model or DEFAULT_DEEPSEEK_MODEL
        base_url = config.llm_base_url or DEFAULT_DEEPSEEK_BASE_URL
        # DeepSeek exposes an OpenAI-compatible Chat Completions + Tool Call API.
        # DeepSeekLlmService additionally tolerates the dict tool schemas the
        # Agent passes (OpenAILlmService alone expects ToolSchema objects).
        return DeepSeekLlmService(
            model=model,
            api_key=config.llm_api_key,
            base_url=base_url,
        )

    raise ValueError(
        f"不支持的 LLM_PROVIDER='{config.llm_provider}'（可选值：mock / deepseek）"
    )
