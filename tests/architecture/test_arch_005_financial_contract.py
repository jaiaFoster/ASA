"""ARCH-005 architecture-decision completeness checks."""
from __future__ import annotations

from pathlib import Path

DOCUMENT = (
    Path(__file__).parents[2] / "architecture/ASA-ARCH-005-Financial-Domain-Contracts.md"
)


def test_arch_005_is_founder_merge_only_and_preserves_instrument_authority() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    assert "Proposed — Founder merge required" in text
    assert "Instrument` and `CanonicalInstrumentIdentity` remain" in text
    assert "sole canonical instrument identity" in text


def test_all_required_contracts_and_strategy_types_are_defined() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    required = {
        "Security",
        "OptionContract",
        "OptionChain",
        "ExpirationCycle",
        "EarningsEvent",
        "EarningsCalendar",
        "VolatilityEvidence",
        "OptionLeg",
        "OptionStructure",
    }
    for name in required:
        assert f"`{name}`" in text or f"## {name}" in text


def test_identity_observation_and_provider_boundaries_are_explicit() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    assert "never identity" in text
    assert "Provider payload" in text
    assert "opaque Maps" in text
    assert "never parse symbols, OCC strings, or provider IDs" in text
    assert "Round-trip serialization must preserve equality and identity" in text


def test_architecture_does_not_authorize_runtime_or_provider_implementation() -> None:
    text = DOCUMENT.read_text(encoding="utf-8")
    assert "does not define provider adapters" in text
    assert "does not define" in text
    assert "live trading" in text
