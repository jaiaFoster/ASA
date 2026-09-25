"""One pure freezing path for every forward-outcome enrollment source.

User tracking (OI-01) and system enrollment (ND-01) both freeze a proposal
through this function, so the frozen identity and JSON for one originating
observation are byte-identical across sources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from asa.contracts.portfolio_lifecycle import ExecutionReadinessArtifact
from strategy_runtime.executable_structures import deserialize_execution_assessment
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.trade_proposal import (
    OptionTradeProposal,
    build_option_trade_proposal,
    trade_proposal_to_data,
)


@dataclass(frozen=True, slots=True)
class FrozenProposal:
    identity: str
    canonical_json: str
    option_symbols: tuple[str, ...]
    # False only for a historical artifact that predates the canonical
    # proposal (or an assessment that is not constructible as intended).
    is_canonical_trade_proposal: bool


def freeze_proposal(
    row: UniversalSignalRow, artifact: ExecutionReadinessArtifact | None
) -> FrozenProposal | None:
    """Freeze the readiness artifact projected from exactly this row, if any."""
    if artifact is None or artifact.originating_observation_id != row.observation_id:
        return None
    payload = json.loads(artifact.canonical_json)
    option_symbols = tuple(
        sorted(
            str(item["instrument_id_value"]).upper()
            for item in payload.get("exact_legs", ())
            if isinstance(item, dict) and item.get("instrument_id_scheme") == "occ"
        )
    )
    try:
        assessment = deserialize_execution_assessment(artifact.assessment_json)
        projected = build_option_trade_proposal(row.to_result(), assessment)
    except (KeyError, TypeError, ValueError):
        # Historical/test artifacts predating the canonical proposal retain
        # their immutable accepted assessment rather than being rewritten.
        projected = None
    if isinstance(projected, OptionTradeProposal):
        return FrozenProposal(
            projected.identity,
            json.dumps(trade_proposal_to_data(projected), sort_keys=True, separators=(",", ":")),
            option_symbols,
            True,
        )
    return FrozenProposal(
        artifact.assessment_identity, artifact.canonical_json, option_symbols, False
    )
