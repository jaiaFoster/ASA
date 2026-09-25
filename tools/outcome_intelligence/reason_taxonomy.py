"""Typed attribution of non-actionable funnel reasons (OI-07).

Every typed reason ASA emits is classified once, here, as:

- ``provider_capability``: the evidence a provider supplies is absent or
  unusable. The capability is named, and so is the data-adequacy gap it
  belongs to.
- ``market_structure_or_policy``: the market or the strategy's declared
  policy rules it out. Better data cannot change it.
- ``strategy_semantics``: a valid evaluation that did not qualify.
- ``asa_internal``: an ASA-owned failure. It is always a defect signal.

A reason missing from this table is reported as ``unclassified``. It is never
silently attributed.
"""

from __future__ import annotations

from dataclasses import dataclass

PROVIDER = "provider_capability"
MARKET = "market_structure_or_policy"
SEMANTICS = "strategy_semantics"
INTERNAL = "asa_internal"
UNCLASSIFIED = "unclassified"

# Keys are data-adequacy-v1 ``capability_gap_matrix[].required_capability``.
GAP_EARNINGS = "confirmed earnings calendar with announcement status and effective timestamps"
GAP_OPTIONS = "complete option expiration, contract, quote, Greek, and implied-volatility evidence"
GAP_ADJUSTED = "split-and-dividend-adjusted or authoritative total-return history"


@dataclass(frozen=True, slots=True)
class ReasonClass:
    category: str
    capability: str | None = None
    gap: str | None = None
    # Whether a better external source could turn the reason into evidence:
    # "yes", "partially" (some instances are real-world absence), or "no".
    paid_data_could_resolve: str = "no"


_TABLE: dict[str, ReasonClass] = {
    # Provider evidence absent or unusable.
    "missing_implied_volatility": ReasonClass(PROVIDER, "option_chain_v1", GAP_OPTIONS, "yes"),
    "missing_actual_delta": ReasonClass(PROVIDER, "option_chain_v1", GAP_OPTIONS, "yes"),
    "unusable_option_chain": ReasonClass(PROVIDER, "option_chain_v1", GAP_OPTIONS, "partially"),
    "unusable_expiration_collection": ReasonClass(
        PROVIDER, "option_chain_v1", GAP_OPTIONS, "partially"
    ),
    "unusable_quote": ReasonClass(PROVIDER, "real_time_quote_v1", GAP_OPTIONS, "partially"),
    # Data-adequacy: some are genuinely unannounced events, which no source knows.
    "missing_earnings_date": ReasonClass(
        PROVIDER, "earnings_calendar_v1", GAP_EARNINGS, "partially"
    ),
    "earnings_clearance": ReasonClass(PROVIDER, "earnings_calendar_v1", GAP_EARNINGS, "partially"),
    "unusable_historical_bars": ReasonClass(PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"),
    "insufficient_historical_bars": ReasonClass(
        PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"
    ),
    "insufficient_adjusted_history": ReasonClass(
        PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"
    ),
    "unusable_total_return_history": ReasonClass(
        PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"
    ),
    "insufficient_total_return_history": ReasonClass(
        PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"
    ),
    "missing_total_return_observation": ReasonClass(
        PROVIDER, "historical_bars_v1", GAP_ADJUSTED, "yes"
    ),
    # Market structure or declared strategy policy.
    "no_valid_expiration_pair": ReasonClass(MARKET),
    "no_usable_expiration_pair": ReasonClass(MARKET),
    "missing_expiration_pair_selection": ReasonClass(MARKET),
    "no_future_expiration": ReasonClass(MARKET),
    "no_expiration_near_target": ReasonClass(MARKET),
    "ambiguous_expiration_tie": ReasonClass(MARKET),
    "selected_expiration_missing": ReasonClass(MARKET),
    "no_put_contracts_at_selected_expiration": ReasonClass(MARKET),
    "no_call_contracts_at_selected_expiration": ReasonClass(MARKET),
    "no_compatible_contract": ReasonClass(MARKET),
    "no_contract_near_target_delta": ReasonClass(MARKET),
    "ambiguous_delta_tie": ReasonClass(MARKET),
    "inverted_spread": ReasonClass(MARKET),
    "non_credit_entry": ReasonClass(MARKET),
    "non_positive_forward_variance": ReasonClass(MARKET),
    "liquidity": ReasonClass(MARKET),
    # Valid evaluations that did not qualify.
    "verdict": ReasonClass(SEMANTICS),
    "no_action": ReasonClass(SEMANTICS),
    # ASA-owned failures.
    "subject_preparation_failed": ReasonClass(INTERNAL),
    "resolution_unresolved": ReasonClass(INTERNAL),
    "execution_readiness_not_available": ReasonClass(INTERNAL),
}

_GAP_PREFIX = "typed unknown evidence gap: "


def reason_code(terminal_reason: str) -> str:
    """Extract the typed code from a funnel ``terminal_reason`` family.

    For example, ``typed unknown evidence gap: missing_earnings_date`` becomes
    ``missing_earnings_date``, and ``earnings_clearance:unknown_unconfirmed``
    becomes ``earnings_clearance``.
    """
    text = terminal_reason.partition(" (")[0].strip()
    if text.startswith(_GAP_PREFIX):
        text = text[len(_GAP_PREFIX) :]
    return text.partition(":")[0].strip()


def classify(code: str) -> ReasonClass:
    return _TABLE.get(code, ReasonClass(UNCLASSIFIED))


def known_gaps() -> frozenset[str]:
    return frozenset(item.gap for item in _TABLE.values() if item.gap is not None)
