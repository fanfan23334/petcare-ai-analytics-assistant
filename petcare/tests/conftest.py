"""Shared pytest fixtures for PetCare tests."""

import sys
from pathlib import Path

import pytest

# make `petcare` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real DeepSeek API tests (requires LLM_API_KEY; not run by default)",
    )


def pytest_collection_modifyitems(config, items):
    """Default runs must NOT call external APIs.

    Integration tests only run when explicitly selected with `-m integration`
    (or an expression containing it). Without an explicit marker expression
    they are skipped regardless of .env state.
    """
    expr = (config.getoption("-m") or "").strip()
    if expr and "integration" in expr:
        return
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(
                pytest.mark.skip(reason="integration tests require `pytest -m integration`")
            )

