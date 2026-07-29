"""STONK-006 official Strategy Library coverage."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_LIBRARY,
    STONK_STRATEGY_MANIFESTS,
    StrategyLibrary,
)
from strategies.errors import ManifestValidationError


def test_library_is_complete_ordered_and_identity_pinned() -> None:
    assert STONK_STRATEGY_LIBRARY.strategy_ids() == (
        "asa.stonk.stock_momentum",
        "earnings_calendar",
        "forward_factor",
        "skew_momentum",
    )
    assert (
        STONK_STRATEGY_LIBRARY.identity
        == StrategyLibrary(tuple(reversed(STONK_STRATEGY_MANIFESTS))).identity
    )
    assert STONK_STRATEGY_LIBRARY.identity == (
        "3b0c3c391880899728dc46bacbf6277913e64dab88973843fa9929ae298575b0"
    )


def test_library_returns_canonical_manifest_without_copy_or_mutation() -> None:
    assert STONK_STRATEGY_LIBRARY.get("earnings_calendar") is EARNINGS_CALENDAR_MANIFEST
    with pytest.raises(KeyError):
        STONK_STRATEGY_LIBRARY.get("unknown.strategy")
    with pytest.raises(AttributeError):
        STONK_STRATEGY_LIBRARY._identity = "changed"  # type: ignore[misc]


def test_library_rejects_empty_duplicate_and_multiple_current_versions() -> None:
    with pytest.raises(ManifestValidationError, match="cannot be empty"):
        StrategyLibrary(())
    with pytest.raises(ManifestValidationError, match="duplicate"):
        StrategyLibrary((EARNINGS_CALENDAR_MANIFEST, EARNINGS_CALENDAR_MANIFEST))
    next_version = replace(EARNINGS_CALENDAR_MANIFEST, strategy_version="1.0.1")
    with pytest.raises(ManifestValidationError, match="one current version"):
        StrategyLibrary((EARNINGS_CALENDAR_MANIFEST, next_version))


def test_strategy_catalog_documents_every_library_entry_and_example() -> None:
    document = (
        Path(__file__).parents[2] / "docs" / "strategies" / "stonk-strategy-library.md"
    ).read_text(encoding="utf-8")
    for strategy_id in STONK_STRATEGY_LIBRARY.strategy_ids():
        assert f"`{strategy_id}`" in document
    assert "STONK_STRATEGY_LIBRARY.get" in document
    assert "dynamic" in document
