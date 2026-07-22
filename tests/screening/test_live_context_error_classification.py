"""TRADIER-PATCH-004: DomainInvariantError classification tests.

classify_domain_invariant_error() distinguishes two DomainInvariantError
causes that both mean "this live request cannot be fulfilled," for
different reasons -- no enabled provider declares the capability at all
(market_data/registry.py::ProviderPriorityPolicy.for_capability() raises
before any provider is selected) versus a provider being selected but the
canonical request subject being incomplete or invalid for it (#156's
original defect class). Message text is the only signal available; these
tests pin the exact strings each real source raises so a future change to
either message would be caught here, not discovered as a silent
misclassification in production.
"""

from __future__ import annotations

from domain import MarketCapability
from domain.values import DomainInvariantError
from screening.live_context import classify_domain_invariant_error


class TestClassifyDomainInvariantError:
    def test_no_priority_policy_classifies_as_no_capable_provider(self) -> None:
        # The exact message market_data/registry.py::ProviderPriorityPolicy
        # .for_capability() raises when no enabled provider declares the
        # capability at all.
        error = DomainInvariantError("No priority policy for option_chain_v1")
        message = classify_domain_invariant_error(error, MarketCapability.OPTION_CHAIN_V1, "AAPL")
        assert message.startswith("no enabled provider declares or satisfies option_chain_v1 for AAPL")
        assert "No priority policy for option_chain_v1" in message

    def test_missing_projection_classifies_as_invalid_acquisition_subject(self) -> None:
        # The exact message domain/market_data.py::MarketDataSubject
        # .projection_for() raises when a selected provider's own lookup
        # finds no matching projection -- #156's original defect.
        error = DomainInvariantError("MarketDataSubject requires one effective provider projection")
        message = classify_domain_invariant_error(error, MarketCapability.OPTION_CHAIN_V1, "AAPL")
        assert "a provider was selected for option_chain_v1 for AAPL" in message
        assert "canonical request subject was incomplete or invalid" in message
        assert "MarketDataSubject requires one effective provider projection" in message

    def test_any_other_domain_invariant_error_also_classifies_as_invalid_acquisition_subject(
        self,
    ) -> None:
        # Every DomainInvariantError a provider's own fetch() can raise
        # before its transport is ever reached (e.g.
        # CapabilityRequest.__post_init__'s various invariants) falls into
        # this category by construction -- only the one specific,
        # known "No priority policy for" message means no provider was
        # ever selected at all.
        error = DomainInvariantError("CapabilityRequest subject required fields mismatch")
        message = classify_domain_invariant_error(error, MarketCapability.OPTION_CHAIN_V1, "AAPL")
        assert "canonical request subject was incomplete or invalid" in message

    def test_symbol_and_capability_are_both_present_in_every_message(self) -> None:
        for error in (
            DomainInvariantError("No priority policy for earnings_calendar_v1"),
            DomainInvariantError("MarketDataSubject requires one effective provider projection"),
        ):
            message = classify_domain_invariant_error(error, MarketCapability.EARNINGS_CALENDAR_V1, "MSFT")
            assert "earnings_calendar_v1" in message
            assert "MSFT" in message
