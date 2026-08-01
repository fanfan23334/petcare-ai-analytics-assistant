"""Shared pytest fixtures for PetCare tests."""

import sys
from pathlib import Path

# make `petcare` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real DeepSeek API tests (requires LLM_API_KEY; not run by default)",
    )

