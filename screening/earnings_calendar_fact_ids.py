"""Earnings Calendar sealed-evidence derived-fact identifiers (SPRINT-014
S14-PR-05).

Deliberately a standalone, side-effect-free module with no other imports:
screening.sealed_earnings_calendar (the acquisition orchestrator, writer)
and strategy_runtime.adapters.earnings_calendar (the acquisition-free
adapter, reader) both import these names, and the adapter must never pull
in acquisition-shaped code even transitively (SubjectAcquisitionPlan,
CapabilityFulfillmentResult, provider/transport types) merely to agree on
a fact's name -- confirmed by tests/architecture that this module imports
nothing beyond the standard library.
"""

from __future__ import annotations

TERM_STRUCTURE_RICHNESS_FACT = "earnings_calendar_term_structure_richness"
IV_REALIZED_RICHNESS_FACT = "earnings_calendar_iv_realized_volatility_richness"
FRONT_EXPIRATION_DATE_FACT = "earnings_calendar_front_expiration_date"
FRONT_DAYS_TO_EXPIRATION_FACT = "earnings_calendar_front_days_to_expiration"
BACK_EXPIRATION_DATE_FACT = "earnings_calendar_back_expiration_date"
BACK_DAYS_TO_EXPIRATION_FACT = "earnings_calendar_back_days_to_expiration"
TARGET_STRIKE_FACT = "earnings_calendar_target_strike"
