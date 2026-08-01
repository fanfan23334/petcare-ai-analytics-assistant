"""Config loading edge cases (no external services)."""

import pytest

import petcare.config as config_mod


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in (
        "MYSQL_PASSWORD",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_DATABASE",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "PETCARE_AS_OF_DATE",
    ):
        monkeypatch.delenv(key, raising=False)
    # isolate from the real petcare/.env file
    monkeypatch.setattr(config_mod, "DOTENV_PATH", tmp_path / ".env-missing")
    yield


def test_missing_mysql_password_raises(monkeypatch):
    with pytest.raises(ValueError, match="MYSQL_PASSWORD"):
        config_mod.load_config()


def test_invalid_port_raises(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "x")
    monkeypatch.setenv("MYSQL_PORT", "not-a-number")
    with pytest.raises(ValueError, match="MYSQL_PORT"):
        config_mod.load_config()


def test_invalid_as_of_date_raises(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "x")
    monkeypatch.setenv("PETCARE_AS_OF_DATE", "2026-13-99")
    with pytest.raises(ValueError, match="PETCARE_AS_OF_DATE"):
        config_mod.load_config()


def test_deepseek_without_key_raises(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "x")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        config_mod.load_config()


def test_defaults(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "x")
    cfg = config_mod.load_config()
    assert cfg.mysql_host == "127.0.0.1"
    assert cfg.mysql_port == 3306
    assert cfg.mysql_user == "root"
    assert cfg.mysql_database == "petcare_db"
    assert cfg.llm_provider == "mock"
    assert cfg.as_of_date.isoformat() == "2026-04-30"


def test_env_values_are_read(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "s3cret")
    monkeypatch.setenv("MYSQL_USER", "petcare_reader")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "sk-live-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    cfg = config_mod.load_config()
    assert cfg.mysql_user == "petcare_reader"
    assert cfg.llm_provider == "deepseek"
    assert cfg.llm_api_key == "sk-live-key"
    assert cfg.llm_model == "deepseek-chat"


def test_dotenv_file_is_loaded_when_present(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MYSQL_PASSWORD=from-dotenv\nLLM_PROVIDER=deepseek\nLLM_API_KEY=sk-dotenv\n", encoding="utf-8")
    config_mod.load_dotenv(env_file)
    import os

    assert os.environ["MYSQL_PASSWORD"] == "from-dotenv"
    assert os.environ["LLM_API_KEY"] == "sk-dotenv"
