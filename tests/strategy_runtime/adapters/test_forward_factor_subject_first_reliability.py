from __future__ import annotations

from typing import cast

import pytest

from domain import MarketCapability, UnknownReason
from market_data.snapshot import MarketSnapshot
from screening.subject_planning import ResolvedEvidenceView
from strategy_runtime.adapters import forward_factor_subject_first


def test_missing_quote_resolution_becomes_typed_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_resolution(
        _snapshot: MarketSnapshot, capability: MarketCapability
    ) -> object:
        raise ValueError(f"snapshot has no resolution for {capability.value}")

    monkeypatch.setattr(forward_factor_subject_first, "resolution_for", _missing_resolution)

    result = forward_factor_subject_first._prepare(
        cast(MarketSnapshot, object()),
        cast(ResolvedEvidenceView, {}),
        (),
        "EQR",
    )

    assert result == UnknownReason("unusable_quote")
