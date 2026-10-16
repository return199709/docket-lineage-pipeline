from __future__ import annotations

import pytest

from efuel_ci.registry import Registry, load_registry


@pytest.fixture(scope="session")
def registry() -> Registry:
    return load_registry()


GOOD = {
    "id": "test_factor",
    "name": "A test factor",
    "value": 2.0,
    "unit": "kgCO2e/kWh",
    "low": 1.0,
    "high": 3.0,
    "source": "Some Report (2024), Table 1, p. 3",
    "url": "https://example.org/report.pdf",
    "vintage": 2024,
    "verification": {"status": "primary", "date": "2026-10-16", "method": "read the table"},
}


@pytest.fixture
def good_factor() -> dict:
    return dict(GOOD)
