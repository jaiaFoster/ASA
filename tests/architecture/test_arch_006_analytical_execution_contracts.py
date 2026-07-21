"""ARCH-006 frozen analytical execution-contract acceptance checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
ARCH = ROOT / "architecture" / "ASA-ARCH-006-Analytical-Execution-Contracts.md"


def _architecture() -> str:
    return ARCH.read_text(encoding="utf-8")


def test_arch_006_defines_complete_owned_pipeline() -> None:
    document = _architecture()
    required = (
        "Position Proposal Engine",
        "PortfolioDelta (proposed)",
        "RiskDecision",
        "Execution Planning Engine",
        "PlannedOrder(s)",
        "SimulationResult",
        "PortfolioDelta (realized)",
        "next PortfolioSnapshot",
    )
    assert all(value in document for value in required)
    assert "Portfolio Engine is the sole calculation owner" in document
    assert "Risk Engine owns evaluation" in document


def test_arch_006_freezes_every_requested_public_contract() -> None:
    document = _architecture()
    required_headings = (
        "### 5.1 Position",
        "### 5.2 Portfolio",
        "### 5.3 PortfolioSnapshot",
        "### 5.4 PortfolioDelta",
        "### 6.1 RiskPolicy",
        "### 6.2 RiskDecision",
        "### 7.1 PlannedOrder",
        "### 7.2 ExecutionPlan",
        "## 8. ExecutionPlanningLifecycle",
    )
    assert all(heading in document for heading in required_headings)
    assert "ExecutionSummary" in document
    assert "PlanningTrace" in document
    assert "PlannedOrderStatus" in document


def test_order_types_prices_and_time_in_force_are_explicit() -> None:
    document = _architecture()
    for value in ("MARKET", "LIMIT", "STOP", "STOP_LIMIT", "DAY", "GTC", "IOC", "FOK"):
        assert value in document
    assert "MARKET | forbidden | forbidden" in document
    assert "LIMIT | required | forbidden" in document
    assert "STOP | forbidden | required" in document
    assert "STOP_LIMIT | required | required" in document


def test_simulation_is_closed_deterministic_and_non_operational() -> None:
    document = _architecture()
    required = (
        "MARKET fills at the first eligible frame",
        "LIMIT BUY/BUY_TO_COVER is eligible",
        "STOP BUY/BUY_TO_COVER triggers",
        "STOP_LIMIT uses the same side-specific trigger",
        "There is no randomness",
        "No module may expose an interface named or behaving as live",
        "live-capable port belongs in Core",
    )
    assert all(value in document for value in required)
    assert "submit, modify, cancel" in document
    assert "broker authentication or write operations" in document


def test_replay_identity_and_provenance_are_complete() -> None:
    document = _architecture()
    for namespace in (
        "asa.position.v1",
        "asa.portfolio.v1",
        "asa.portfolio_snapshot.v2",
        "asa.portfolio_delta.v1",
        "asa.risk_policy.v1",
        "asa.risk_decision.v1",
        "asa.planned_order.v1",
        "asa.execution_plan.v2",
        "asa.execution_planning_lifecycle.v1",
        "asa.simulation_result.v1",
    ):
        assert namespace in document
    assert "reproduce exact IDs" in document
    assert "Evidence is a non-empty canonical tuple" in document


def test_strategy_policy_has_explicit_propagation_and_cannot_weaken_platform_policy() -> None:
    document = _architecture()
    assert "attach an immutable\ntuple of Strategy-scoped `RiskPolicy`" in document
    assert "Position Proposal preserves the same policy" in document
    assert "Strategy cannot emit a\nPlatform-scoped policy" in document
    assert "may omit policy or add stricter limits only" in document


def test_pre_simulation_cash_effect_is_evidence_based_and_required() -> None:
    document = _architecture()
    assert "cash_change               signed MonetaryAmount" in document
    assert "estimates proposed and approved cash/buying-power effects" in document
    assert "explicit valuation and price multiplier" in document
    assert "Simulated deltas replace the estimates" in document


def test_new_position_inputs_have_canonical_owners() -> None:
    document = _architecture()
    assert "account_id                one canonical ASA account identity" in document
    assert "InstrumentValuation" in document
    assert "quantity_increment        positive Decimal" in document
    assert "Portfolio account supplies new-position account selection" in document
    assert "no Strategy, proposal, ID parser" in document
    assert "raw_target_quantity = desired_exposure / unit_exposure" in document
    assert "snapshot-independent fraction" in document
    assert "contains\nno reference capital" in document
    assert "Portfolio Engine reads the\nsource Snapshot" in document
    assert "rounds toward zero" in document
    assert "result below one increment is zero" in document
    assert "emits an evidenced analytical no-op result" in document
    assert "abs(maximum_loss) / capital_required" in document
    assert "non-positive `maximum_loss`" in document
    assert "PortfolioEvaluationResult" in document
    assert "DELTA_PRODUCED | NO_CHANGE" in document
    assert "Risk and Planning accept only DELTA_PRODUCED results" in document
    assert "does not change Proposed Position identity" in document
    assert "V1 is explicitly single-account and USD-only" in document
    assert "currency is never inferred from a\nDecimal" in document
    assert "maximum_loss` as USD Decimals" in document


def test_risk_schemas_composition_and_evidence_are_closed() -> None:
    document = _architecture()
    for parameter in (
        "minimum_remaining_amount: MonetaryAmount",
        "minimum_cash_ratio: Decimal",
        "maximum_ratio: Decimal",
        "allow_increase_existing: bool",
        "maximum_amount: MonetaryAmount",
    ):
        assert parameter in document
    assert "non-positive denominator rejects every ratio policy" in document
    assert "greater\nminimum wins" in document
    assert "lesser maximum wins" in document
    assert "only the Evidence\nactually consumed" in document
    assert "finite target-quantity lattice" in document
    assert "first\npassing candidate is the greatest permitted target" in document
    assert "scaled projected maximum loss are all recomputed" in document
    assert "Zero is\nnot represented as REDUCE" in document


def test_parent_child_identities_are_acyclic() -> None:
    document = _architecture()
    planned_order = document.split("### 7.1 PlannedOrder", maxsplit=1)[1].split(
        "### 7.2 ExecutionPlan", maxsplit=1
    )[0]
    lifecycle = document.split("## 8. ExecutionPlanningLifecycle", maxsplit=1)[1].split(
        "## 9. Deterministic simulation", maxsplit=1
    )[0]
    assert "execution_plan_id" not in planned_order
    assert "risk_decision_id" in planned_order
    assert "does not\ncontain or hash the not-yet-derived Execution Plan ID" in document
    assert "does not\ncontain the lifecycle ID" in lifecycle
    assert "lifecycle identity is derived last" in lifecycle
    assert "ORDER_SIMULATED_*" not in lifecycle
    assert "`ORDER_SIMULATED`" in lifecycle
    assert "`ExecutionPlanningEventType` is exactly" in lifecycle
    for namespace in (
        "asa.planning_trace.v1",
        "asa.planning_trace_event.v1",
        "asa.execution_planning_event.v1",
        "asa.simulated_order_state.v1",
        "asa.simulation_trace_event.v1",
    ):
        assert namespace in document


def test_simulation_state_liquidity_and_time_in_force_are_complete() -> None:
    document = _architecture()
    for value in (
        "SimulatedOrderState",
        "SimulationTraceEvent",
        "local immutable-successor liquidity ledger",
        "DAY_EXPIRED",
        "IOC_REMAINDER_CANCELLED",
        "consumes no liquidity",
        "retaining explicit remaining",
        "A STOP or STOP_LIMIT trigger frame may also fill",
        "filled plus remaining quantity equals Planned Order quantity",
        "SimulationTraceEventType` is exactly",
        "SimulationTerminalReason` is exactly",
    ):
        assert value in document


def test_import_matrix_is_code_direction_not_pipeline_direction() -> None:
    document = _architecture()
    assert "pipeline arrows in Section 3 show value flow, not Python import permission" in document
    assert "| `portfolio` | itself, `domain` |" in document
    assert "| `risk` | itself, `domain` |" in document
    assert "| `execution_planning` | itself, `domain` |" in document
    assert "| `simulation` | itself, `domain`, pure public functions from `portfolio` |" in document
    assert "All other imports between these operational packages are prohibited" in document


def test_portfolio_calculation_and_multiplier_semantics_have_one_owner() -> None:
    document = _architecture()
    assert "### 5.5 Portfolio Engine v1 calculation semantics" in document
    assert "unit_value = current_price_per_unit × price_multiplier" in document
    assert "realized P&L for a long reduction" in document
    assert "realized P&L for a short cover" in document
    assert "buying-power change equals cash change" in document
    assert (
        "net liquidation value is cash plus long market value minus short market value" in document
    )
    assert "`SELL_SHORT` is therefore not a v1 Planned Order side" in document
    assert "quantity × simulated_fill_price × price_multiplier" in document
    assert "Portfolio realized P&L is cumulative ledger state" in document
    assert "it is not the sum of active Position realized P&L" in document


def test_contract_migration_rejects_dual_state_and_compatibility_shims() -> None:
    document = _architecture()
    assert "It replaces the operational-domain name `Holding`" in document
    assert "`PlannedOrder` replaces the misleading v1 name `BrokerRequest`" in document
    assert "no alias or compatibility shim" in document
    assert "`main` always has exactly one canonical" in document
    assert "never exposes dual state or a compatibility shim" in document
    assert "one\natomic migration cohort and one PR" in document
    assert "cannot merge any\nticket independently" in document


def test_canonical_glossary_and_vision_use_arch_006_terms() -> None:
    glossary = (ROOT / "architecture" / "DOMAIN_GLOSSARY.md").read_text(encoding="utf-8")
    vision = (ROOT / "architecture" / "ARCHITECTURE_VISION.md").read_text(encoding="utf-8")
    assert "**Broker Request**" not in glossary
    assert "**Portfolio Decision**" not in glossary
    for term in ("**Planned Order**", "**Portfolio Delta**", "**Risk Decision**"):
        assert term in glossary
    assert "ExecutionPlan + PlannedOrder(s)" in vision
    assert "Simulation Engine" in vision


def test_adr_009_uses_snapshot_independent_proposal_sizing() -> None:
    adr = (ROOT / "architecture" / "ADR-009-execution-semantics.md").read_text(encoding="utf-8")
    assert "snapshot-independent decimal fraction" in adr
    assert "no reference capital, Portfolio identity" in adr
    assert "Portfolio Engine alone derives sizing reference capital" in adr
    assert "reference-capital and sizing\npolicy values must be present" not in adr


def test_arch_006_is_founder_gated_and_does_not_authorize_implementation_merge() -> None:
    document = _architecture()
    assert "Status:** Proposed — Founder merge required" in document
    assert "Founder merge freezes these public contracts" in document
    assert "No deployment" in document
    assert "live\ntrading capability is authorized" in document
