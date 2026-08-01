"""LLM provider factory tests (no external API calls)."""

import pytest

from datetime import date

from petcare.config import PetCareConfig
from petcare.deepseek_llm import DeepSeekLlmService
from petcare.llm_factory import create_llm_service
from petcare.mock_llm import PetCareMockLlmService


def _config(**overrides) -> PetCareConfig:
    base = dict(
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="petcare_reader",
        mysql_password="secret",
        mysql_database="petcare_db",
        llm_provider="mock",
        llm_model="",
        llm_api_key="",
        llm_base_url="",
        as_of_date=date(2026, 4, 30),
    )
    base.update(overrides)
    return PetCareConfig(**base)


def test_mock_provider_returns_mock_service():
    svc = create_llm_service(_config())
    assert isinstance(svc, PetCareMockLlmService)


def test_deepseek_provider_uses_openai_compatible_service():
    svc = create_llm_service(
        _config(
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            llm_api_key="sk-test",
            llm_base_url="https://api.deepseek.com",
        )
    )
    assert isinstance(svc, DeepSeekLlmService)
    assert svc.model == "deepseek-chat"
    assert "api.deepseek.com" in str(svc._client.base_url)


def test_deepseek_default_model_and_base_url():
    svc = create_llm_service(
        _config(llm_provider="deepseek", llm_api_key="sk-test")
    )
    assert svc.model == "deepseek-chat"
    assert "api.deepseek.com" in str(svc._client.base_url)


def test_deepseek_missing_key_raises_clear_error():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        create_llm_service(_config(llm_provider="deepseek"))


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        create_llm_service(_config(llm_provider="gpt3"))
