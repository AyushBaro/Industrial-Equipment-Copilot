"""Shared fixtures: build the database + hierarchy once per test session."""
from __future__ import annotations

import pytest

from src import config
from src.data import load_cmapss
from src.data.asset_hierarchy import build_hierarchy, load_hierarchy
from src.data.detect_flat_sensors import compute_flat_sensors


@pytest.fixture(scope="session", autouse=True)
def _built_artifacts():
    """Rebuild DuckDB + flat-sensor evidence + asset hierarchy from raw data."""
    load_cmapss.build_database()
    compute_flat_sensors()
    build_hierarchy()
    yield


@pytest.fixture(scope="session")
def con():
    c = load_cmapss.connect(read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="session")
def hierarchy():
    return load_hierarchy()
