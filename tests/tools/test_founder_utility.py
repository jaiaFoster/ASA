from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from asa.api.screening_models import ExecutableStructureAssessmentResponse
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.portfolio_lifecycle import ExecutionReadinessArtifact
from strategy_runtime.executable_structures import serialize_execution_assessment
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_screening_routes import _record
from tests.strategy_runtime.test_option_payoff import _vertical
from tests.strategy_runtime.test_trade_proposal import _assessment as _calendar
from tools.options_product.founder_utility import (
    COMPLETE_TRADE_CARD,
    INCOMPLETE_PRESENTATION,
    PATH_DEFECT,
    TYPED_FAILURE_PRESENTATION,
    capture_founder_utility,
    summarize,
    trade_card_gaps,
)

NOW = datetime(2026, 9, 24, 18, tzinfo=UTC)
SHA = "b" * 40
TOKEN = "replay-token"


class _ReadinessRepository:
    def __init__(self, *artifacts: ExecutionReadinessArtifact) -> None:
        self._artifacts = {(item.strategy_id, item.symbol): item for item in artifacts}

    def execution_readiness(self, strategy_id: str, symbol: str):  # type: ignore[no-untyped-def]
        return self._artifacts.get((strategy_id, symbol))


def _artifact(signal: str, symbol: str, assessment) -> ExecutionReadinessArtifact:  # type: ignore[no-untyped-def]
    assessment = replace(assessment, originating_result_identity=f"{signal}-{symbol}-obs")
    return ExecutionReadinessArtifact(
        assessment.originating_result_identity,
        signal,
        symbol,
        assessment.identity,
        ExecutableStructureAssessmentResponse.from_assessment(assessment).model_dump_json(),
        serialize_execution_assessment(assessment),
        assessment.assessed_at,
    )


def _replay_fetch(*artifacts: ExecutionReadinessArtifact, extra_rows=()):  # type: ignore[no-untyped-def]
    results = InMemoryLatestResultRepository()
    for row in (
        _record("skew_momentum", "AAPL"),
        _record("earnings_calendar", "AAPL"),
        _record("forward_factor", "MSFT"),
        _record("forward_factor", "XYZ", "no_signal", verdict="FAIL"),
        _record("B001", "AAPL"),
        *extra_rows,
    ):
        results.upsert(row)
    client = TestClient(
        build_application(
            Settings(agent_api_token=TOKEN, release_sha=SHA, _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(),
                latest_result_repository=results,
                portfolio_lifecycle_repository=_ReadinessRepository(*artifacts),  # type: ignore[arg-type]
            ),
        )
    )
    paths: list[str] = []

    def fetch(path: str):  # type: ignore[no-untyped-def]
        paths.append(path)
        response = client.get(path, headers={"Authorization": f"Bearer {TOKEN}"})
        return response.status_code, response.json()

    return fetch, paths


def _replay_artifacts() -> tuple[ExecutionReadinessArtifact, ...]:
    return (
        _artifact("skew_momentum", "AAPL", _vertical()),
        _artifact("earnings_calendar", "AAPL", _calendar()),
        _artifact("forward_factor", "MSFT", _calendar(compatible=False)),
    )


def test_replay_traverses_real_product_surfaces_for_every_qualifying_option_result() -> None:
    fetch, paths = _replay_fetch(*_replay_artifacts())

    artifact = capture_founder_utility(fetch, production_sha=SHA, captured_at=NOW)

    by_key = {(item["signal_id"], item["symbol"]): item for item in artifact["observations"]}
    assert set(by_key) == {
        ("skew_momentum", "AAPL"),
        ("earnings_calendar", "AAPL"),
        ("forward_factor", "MSFT"),
    }
    vertical = by_key[("skew_momentum", "AAPL")]
    assert vertical["outcome"] == COMPLETE_TRADE_CARD
    assert vertical["gaps"] == []
    assert vertical["leg_count"] == 2
    assert vertical["payoff_state"] == "deterministic_terminal_payoff"
    calendar = by_key[("earnings_calendar", "AAPL")]
    assert calendar["outcome"] == COMPLETE_TRADE_CARD
    # Calendar legs expire on different dates; the typed refusal is truthful.
    assert calendar["payoff_state"].startswith("typed_unavailable:")
    blocked = by_key[("forward_factor", "MSFT")]
    assert blocked["outcome"] == TYPED_FAILURE_PRESENTATION
    assert blocked["reason_code"] == "no_compatible_contract"
    assert blocked["blocker_category"] == "contract_selection"
    assert artifact["verdict"] == "complete_trade_card_path_observed"
    assert artifact["outcome_counts"] == {
        COMPLETE_TRADE_CARD: 2,
        TYPED_FAILURE_PRESENTATION: 1,
    }
    assert artifact["signals"]["B001"]["declares_option_structure"] is False
    assert artifact["signals"]["forward_factor"]["qualifying_verdict_count"] == 1
    # Read-only: no refresh, tracking, or any other mutating surface is touched.
    assert not any("refresh" in path or "tracked-candidates" in path for path in paths)
    assert not any("XYZ" in path for path in paths)


def test_replay_is_deterministic_for_identical_state() -> None:
    first = capture_founder_utility(
        _replay_fetch(*_replay_artifacts())[0], production_sha=SHA, captured_at=NOW
    )
    second = capture_founder_utility(
        _replay_fetch(*_replay_artifacts())[0], production_sha=SHA, captured_at=NOW
    )

    assert first == second


def test_qualifying_result_without_current_readiness_is_a_path_defect() -> None:
    artifacts = _replay_artifacts()[:2]
    fetch, _ = _replay_fetch(*artifacts)

    artifact = capture_founder_utility(fetch, production_sha=SHA, captured_at=NOW)

    missing = next(
        item for item in artifact["observations"] if item["signal_id"] == "forward_factor"
    )
    assert missing["outcome"] == PATH_DEFECT
    assert missing["gaps"] == ["trade_proposal_http_404:NO_EXECUTION_READINESS"]
    assert artifact["verdict"] == "defect_reopen_correction"


def test_capture_refuses_unexpected_deployment_sha() -> None:
    fetch, paths = _replay_fetch(*_replay_artifacts())

    with pytest.raises(RuntimeError, match="deployed SHA mismatch"):
        capture_founder_utility(fetch, production_sha="c" * 40, captured_at=NOW)
    assert paths == ["/api/v1/version"]


def test_trade_card_gaps_require_typed_absence_and_both_quote_sides() -> None:
    proposal = {
        "proposal_identity": "p",
        "originating_result_identity": "r",
        "underlying": "AAPL",
        "strategy_id": "s",
        "strategy_version": "1",
        "structure": "vertical",
        "modeled_net_debit_or_credit": "2.00",
        "entry_model_version": "m",
        "entry_calculated_at": "2026-09-24T18:00:00Z",
        "liquidity": "unknown",
        "evidence_snapshot_identity": "e",
        "constructibility": "constructible_as_intended",
        "assumptions": ["a"],
        "rationale": ["r"],
        "risk_notes": ["n"],
        "invalidation_notes": ["not_defined_by_strategy"],
        "legs": [
            {
                "canonical_contract_identity": "occ",
                "buy_or_sell": "buy",
                "call_or_put": "call",
                "strike": "100",
                "expiration": "2026-10-16",
                "quantity": "1",
                "bid": None,
                "ask": "2",
                "midpoint": "1.5",
                "quote_observed_at": "2026-09-24T18:00:00Z",
            }
        ],
        "capital_required": {"state": "unknown", "value": None, "reason": None},
        "maximum_loss": {"state": "supported", "value": "200", "reason": None},
        "maximum_profit": {"state": "undefined", "value": None, "reason": "unbounded"},
        "breakeven": {"state": "bogus", "value": None, "reason": None},
    }

    assert trade_card_gaps(proposal) == [
        "leg[0].invalid:midpoint_without_bid_ask",
        "untyped_absence:capital_required",
        "invalid:breakeven",
    ]


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        ((), "bounded_no_signal"),
        ((TYPED_FAILURE_PRESENTATION,), "typed_failure_path_only_awaiting_constructible"),
        ((COMPLETE_TRADE_CARD, TYPED_FAILURE_PRESENTATION), "complete_trade_card_path_observed"),
        ((COMPLETE_TRADE_CARD, INCOMPLETE_PRESENTATION), "defect_reopen_correction"),
        ((PATH_DEFECT,), "defect_reopen_correction"),
    ],
)
def test_summary_verdict_is_closed_and_defect_dominant(
    outcomes: tuple[str, ...], verdict: str
) -> None:
    assert summarize([{"outcome": item} for item in outcomes]) == verdict
