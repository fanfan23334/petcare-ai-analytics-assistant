"""PetCare configuration: environment variables + optional .env file.

Secrets (MySQL password, LLM API key) are NEVER hardcoded here. Read from:
1. real environment variables (highest priority)
2. petcare/.env file (simple KEY=VALUE parser, no third-party dependency)

Missing required config raises a clear error with the variable name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DOTENV_PATH = Path(__file__).resolve().parent / ".env"


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env without overriding existing env vars."""
    path = path or DOTENV_PATH
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(
            f"missing required config: {name} (set the environment variable "
            f"or add it to {DOTENV_PATH})"
        )
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class PetCareConfig:
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    llm_provider: str
    llm_model: str
    llm_api_key: str
    llm_base_url: str
    as_of_date: date


def load_config() -> PetCareConfig:
    load_dotenv()

    mysql_password = _require("MYSQL_PASSWORD")

    try:
        mysql_port = int(_optional("MYSQL_PORT", "3306"))
    except ValueError as exc:
        raise ValueError(f"invalid MYSQL_PORT: {os.getenv('MYSQL_PORT')}") from exc

    as_of_date_raw = _optional("PETCARE_AS_OF_DATE", "2026-04-30")
    try:
        as_of_date = date.fromisoformat(as_of_date_raw)
    except ValueError as exc:
        raise ValueError(
            f"invalid PETCARE_AS_OF_DATE '{as_of_date_raw}': expected YYYY-MM-DD"
        ) from exc

    llm_provider = _optional("LLM_PROVIDER", "mock").lower()
    llm_api_key = _optional("LLM_API_KEY")
    llm_model = _optional("LLM_MODEL")
    llm_base_url = _optional("LLM_BASE_URL")
    if llm_provider != "mock" and not llm_api_key and llm_provider != "ollama":
        raise ValueError(
            f"missing required config: LLM_API_KEY for provider '{llm_provider}' "
            f"(set LLM_API_KEY or use LLM_PROVIDER=mock)"
        )

    return PetCareConfig(
        mysql_host=_optional("MYSQL_HOST", "127.0.0.1"),
        mysql_port=mysql_port,
        mysql_user=_optional("MYSQL_USER", "root"),
        mysql_password=mysql_password,
        mysql_database=_optional("MYSQL_DATABASE", "petcare_db"),
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        as_of_date=as_of_date,
    )
