"""Shared pytest fixtures for PetCare tests."""

import sys
from pathlib import Path

# make `petcare` importable regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
