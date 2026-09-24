"""SL-02 SPY 30-DTE put credit spread: preparation, graph verdict, exact
trade proposal, deterministic payoff, and typed UNKNOWNs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderProvenance,
    UnknownReason,
    market_observation_identity,
)
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import (
    CapabilityRequest,
    ProviderIdentity,
    ProviderMetadata,
    ProviderStatus,
)
from market_data.resolution import ResolutionPolicy
from market_data.subject_snapshot import seal_subject_snapshot
from strategies.put_credit_spread_planning import select_target_expiration
from strategy_runtime.adapters.put_credit_spread import SPY_PUT_CREDIT_SPREAD_CONTRACT
from strategy_runtime.adapters.put_credit_spread_subject_first import (
    _build_execution_assessment,
    _prepare,
    build_put_credit_spread_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.executable_structures import ExecutableStructureStatus
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry
from strategy_runtime.option_payoff import default_terminal_payoff_grid, model_terminal_payoff
from strategy_runtime.result import EvaluationState
from strategy_runtime.trade_proposal import OptionTradeProposal, build_option_trade_proposal
from tests.domain.test_financial_contracts import security
from tests.strategy_runtime.adapters.test_stock_benchmarks_subject_first import (
    NOW,
    _Clock,
    _quote,
)

SYMBOL = "SPY"
EXPIRY = date(2026, 10, 5)  # 30 calendar days after NOW (2026-09-05)
_SECURITY = security(SYMBOL)
_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain", 1),)
_POLICY = {
    MarketCapability.REAL_TIME_QUOTE_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("last",)),
    MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("contracts",)),
}
_METADATA = tuple(
    ProviderMetadata(
        ProviderIdentity("tradier", "test_provider", "v1"), (capability,), (), (capability,), "v1"
    )
    for capability in _POLICY
)


def _put(strike: str, delta: str | None, bid: str, ask: str) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"SPY-{EXPIRY}-{strike}-P"),
        _SECURITY,
        EXPIRY,
        Decimal(strike),
        OptionType.PUT,
        Decimal(bid),
        Decimal(ask),
        (Decimal(bid) + Decimal(ask)) / 2,
        500,
        5000,
        None if delta is None else Decimal(delta),
        None,
        None,
        None,
        None,
        Decimal("0.18"),
        NOW,
        _EVIDENCE,
    )


def _single_result(
    capability: MarketCapability, required_fields: tuple[str, ...], value: object
) -> CapabilityFulfillmentResult:
    subject_type = (
        MarketDataSubjectType.OPTION_UNDERLYING
        if capability is MarketCapability.OPTION_CHAIN_V1
        else MarketDataSubjectType.INSTRUMENT
    )
    subject = MarketDataSubject(
        _SECURITY.instrument,
        subject_type,
        capability,
        MarketDataRequestContext(NOW, NOW, required_fields, (), _EVIDENCE),
    )
    identity = market_observation_identity("tradier", capability, subject, NOW, value, "v1")
    observation = MarketObservation(
        identity,
        capability,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        ProviderProvenance("tradier", "tradier-request", _EVIDENCE),
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(required_fields, required_fields, ()),
    )
    request = CapabilityRequest(capability, (subject,), NOW, NOW, required_fields, 3600)
    attempt = ProviderFulfillmentAttempt(
        "tradier", 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, "tradier", (observation,), (attempt,), True
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("chain-spy", _SECURITY, NOW, contracts, _EVIDENCE)


_FULL_CHAIN = _chain(
    _put("620", "-0.45", "9.80", "10.00"),
    _put("600", "-0.30", "5.00", "5.20"),
    _put("590", "-0.20", "3.10", "3.30"),
    _put("580", "-0.10", "1.90", "2.10"),
    _put("560", "-0.05", "0.90", "1.10"),
)


def _snapshot(chain: OptionChain):
    return seal_subject_snapshot(
        (
            _single_result(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), _quote(Decimal("630"))),
            _single_result(MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain),
        ),
        as_of=NOW,
        required_capabilities=tuple(_POLICY),
        resolution_policy_by_capability=_POLICY,
        provider_metadata=_METADATA,
    )


def _knowledge(chain: OptionChain = _FULL_CHAIN):
    snapshot = _snapshot(chain)
    mapping = _prepare(NOW, snapshot, {}, (("expiration", EXPIRY.isoformat()),), SYMBOL)
    assert not isinstance(mapping, UnknownReason)
    registry = KnowledgeCompositionRegistry((("spy_put_credit_spread", mapping),))
    knowledge = compose_strategy_knowledge(
        snapshot, registry, "spy_put_credit_spread", subject=SYMBOL
    )
    assert not isinstance(knowledge, UnknownReason)
    return knowledge


def _result(knowledge):  # type: ignore[no-untyped-def]
    adapter = build_put_credit_spread_subject_first_adapter({SYMBOL: knowledge})
    return adapter(
        RuntimeContext(
            contract=SPY_PUT_CREDIT_SPREAD_CONTRACT, subject=SYMBOL, clock=_Clock(), run_id="run-1"
        )
    )


def test_source_legs_resolve_to_an_exact_credit_spread_proposal() -> None:
    knowledge = _knowledge()
    assert knowledge.payload.days_to_expiration == 30
    result = _result(knowledge)

    assert result.verdict == "PASS"
    assert result.evaluation_state is EvaluationState.PASS
    assert "source_one_active_position_rule_not_evaluated_by_screener" in result.warnings

    assessment = _build_execution_assessment(knowledge, result, NOW)
    assert assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    proposal = build_option_trade_proposal(
        result.to_result() if hasattr(result, "to_result") else result, assessment
    )
    assert isinstance(proposal, OptionTradeProposal)
    legs = {leg.buy_or_sell: leg for leg in proposal.legs}
    assert legs["sell"].strike == Decimal("600") and legs["sell"].call_or_put == "put"
    assert legs["buy"].strike == Decimal("580")
    # Credit of 5.10 - 2.00 = 3.10 at the modeled midpoint.
    assert proposal.modeled_net_debit_or_credit == Decimal("-3.10")
    # Deterministic bounds: max loss (20 - 3.10) x 100; max profit 3.10 x 100.
    assert proposal.maximum_loss.value == Decimal("1690.00")
    assert proposal.maximum_profit.value == Decimal("310.00")
    assert proposal.breakeven.value == Decimal("596.9")
    payoff = model_terminal_payoff(
        assessment=assessment, underlying_price_grid=default_terminal_payoff_grid(assessment)
    )
    assert payoff.points[0].payoff == Decimal("-1690.00")  # type: ignore[union-attr]


def test_replay_of_the_same_sealed_snapshot_is_identical() -> None:
    first, second = _knowledge(), _knowledge()

    assert first.canonical_facts == second.canonical_facts
    assert _result(first).metrics == _result(second).metrics


@pytest.mark.parametrize(
    ("chain", "reason"),
    [
        (_chain(), "no_put_contracts_at_selected_expiration"),
        (
            _chain(_put("600", None, "5", "5.2"), _put("580", None, "1.9", "2.1")),
            "missing_actual_delta",
        ),
        (_chain(_put("600", "-0.30", "5", "5.2")), "missing_actual_delta"),
    ],
)
def test_missing_evidence_is_typed_unknown(chain: OptionChain, reason: str) -> None:
    mapping = _prepare(NOW, _snapshot(chain), {}, (("expiration", EXPIRY.isoformat()),), SYMBOL)

    assert isinstance(mapping, UnknownReason)
    assert mapping.code == reason


def test_expiration_selection_never_breaks_a_tie() -> None:
    today = date(2026, 9, 5)
    assert select_target_expiration((date(2026, 10, 5), date(2026, 10, 9)), today) == date(
        2026, 10, 5
    )
    tie = select_target_expiration((date(2026, 10, 3), date(2026, 10, 7)), today)
    assert isinstance(tie, UnknownReason) and tie.code == "ambiguous_expiration_tie"
    past = select_target_expiration((date(2026, 9, 1),), today)
    assert isinstance(past, UnknownReason) and past.code == "no_future_expiration"


def test_trade_card_uses_the_graphs_exact_contracts() -> None:
    from strategy_runtime.adapters.put_credit_spread_subject_first import _graph_outputs, _legs

    knowledge = _knowledge()
    assessment = _build_execution_assessment(knowledge, _result(knowledge), NOW)
    long, short = _legs(_graph_outputs(_FULL_CHAIN, EXPIRY).get("structure").value)

    assert {item.canonical_contract_identity for item in assessment.exact_legs} == {
        long.identity,
        short.identity,
    }


@pytest.mark.parametrize(
    ("chain", "reason"),
    [
        # Review probe 1: one contract nearest both targets; the short leg
        # would fall to a far-off delta, never silently accepted.
        (
            _chain(_put("580", "-0.10", "1.9", "2.1"), _put("575", "-0.08", "1.5", "1.7")),
            "no_contract_near_target_delta",
        ),
        # Review probe 2: non-monotonic deltas invert the spread.
        (
            _chain(_put("580", "-0.30", "5", "5.2"), _put("600", "-0.10", "1.9", "2.1")),
            "inverted_spread",
        ),
        # Review probe 3: the long leg is nowhere near the 0.10 delta target.
        (
            _chain(_put("600", "-0.30", "5", "5.2"), _put("598", "-0.28", "4.8", "5.0")),
            "no_contract_near_target_delta",
        ),
        # Exact delta tie on the short leg is never broken silently.
        (
            _chain(
                _put("600", "-0.30", "5", "5.2"),
                _put("605", "-0.30", "5.5", "5.7"),
                _put("580", "-0.10", "1.9", "2.1"),
            ),
            "ambiguous_delta_tie",
        ),
        # A spread that would not collect a credit is not this strategy.
        (
            _chain(_put("600", "-0.30", "1.0", "1.2"), _put("580", "-0.10", "1.9", "2.1")),
            "non_credit_entry",
        ),
    ],
)
def test_selection_that_is_not_the_source_credit_spread_is_typed_unknown(
    chain: OptionChain, reason: str
) -> None:
    mapping = _prepare(NOW, _snapshot(chain), {}, (("expiration", EXPIRY.isoformat()),), SYMBOL)

    assert isinstance(mapping, UnknownReason)
    assert mapping.code == reason


def test_expiration_far_from_thirty_days_is_typed_unknown() -> None:
    far = select_target_expiration((date(2026, 10, 20),), date(2026, 9, 5))
    assert isinstance(far, UnknownReason) and far.code == "no_expiration_near_target"


def test_expand_demands_requests_only_the_selected_chain() -> None:
    from domain import (
        EvidenceUsability,
        ExpirationCollection,
        ExpirationCycle,
        FreshnessStatus,
        ResolvedCapabilityEvidence,
    )
    from strategies.put_credit_spread_planning import expand_demands, expirations_demand

    missing = expand_demands({}, now=NOW)
    assert [item.code for item in missing.unknown_reasons] == ["no_future_expiration"]

    today = NOW.date()
    cycles = tuple(
        ExpirationCycle(item, (item - today).days, False, True, today, _EVIDENCE)
        for item in (date(2026, 9, 19), EXPIRY, date(2026, 10, 16))
    )
    discovery = expirations_demand(NOW)
    evidence = {
        discovery.demand_id: ResolvedCapabilityEvidence(
            discovery.demand_id,
            MarketCapability.OPTION_CHAIN_V1,
            EvidenceUsability.RESOLVED,
            ExpirationCollection(today, cycles),
            ("obs-1",),
            FreshnessStatus.FRESH,
        )
    }

    expansion = expand_demands(evidence, now=NOW)

    assert expansion.selections == (("expiration", EXPIRY.isoformat()),)
    assert [item.expiration for item in expansion.demands] == [EXPIRY]
    assert not expansion.unknown_reasons


def test_results_disclose_tolerances_as_proposal_assumptions() -> None:
    knowledge = _knowledge()
    result = _result(knowledge)
    proposal = build_option_trade_proposal(
        result, _build_execution_assessment(knowledge, result, NOW)
    )

    assert isinstance(proposal, OptionTradeProposal)
    assert "leg_delta_within_0.05_of_source_target" in proposal.assumptions
    assert "expiration_within_7_days_of_30_dte" in proposal.assumptions
    assert "source_one_active_position_rule_not_evaluated_by_screener" in proposal.assumptions
