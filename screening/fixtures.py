"""Fixed, deterministic canonical fixture data for screening adapters (SCREEN-004).

No symbol, provider, or live market-data access is involved -- every value
here is a hard-coded, previously-reviewed, safe fixture, matching the same
pattern already used for live Market Data Platform validation subjects
(asa.market_data_ops.subjects). Live acquisition is explicitly deferred to
a successor sprint (SPRINT-007); this sprint's screening runs are
fixture-backed only, per SCREEN-004's own scope.

Each target strategy's manifest enforces its own DTE (days-to-expiration)
window, so each gets its own fixture expirations/chain rather than sharing
one -- forcing one generic pair to satisfy every manifest's constraints
would be fragile and less legible than naming each explicitly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    AnnouncementTime,
    CanonicalInstrumentIdentity,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)

SAFE_SYMBOL = "AAPL"
OBSERVED_AT = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
AS_OF_DATE = date(2026, 7, 22)

EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, f"screening:fixture:{SAFE_SYMBOL}"),)


def fixture_security(symbol: str = SAFE_SYMBOL) -> Security:
    return Security(
        Instrument(
            CanonicalInstrumentIdentity("figi", f"figi-{symbol}"),
            InstrumentKind.EQUITY,
            symbol,
            "USD",
        ),
        symbol,
        SecurityAssetType.EQUITY,
        "XNAS",
    )


def fixture_contract(
    option_id: str,
    expiration: date,
    strike: str,
    option_type: OptionType,
    delta: str,
    mark: str,
    *,
    implied_volatility: str = "0.30",
) -> OptionContract:
    mark_value = Decimal(mark)
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", option_id),
        fixture_security(),
        expiration,
        Decimal(strike),
        option_type,
        mark_value - Decimal("0.10"),
        mark_value + Decimal("0.10"),
        mark_value,
        100,
        500,
        Decimal(delta),
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("0.01"),
        Decimal(implied_volatility),
        OBSERVED_AT,
        EVIDENCE,
    )


# --- earnings_calendar: front_min/max_dte=7/21, back_min/max_dte=22/75, and the
# front expiration must fall before the earnings date while back falls after it --

EARNINGS_EVENT_DATE = date(2026, 8, 5)  # +14 days from AS_OF_DATE
EARNINGS_FRONT_EXPIRATION = date(2026, 7, 31)  # +9 days; before the earnings date
EARNINGS_BACK_EXPIRATION = date(2026, 9, 18)  # +58 days; after the earnings date


def earnings_calendar_chain() -> OptionChain:
    contracts = (
        fixture_contract(
            "ec-front-call-100", EARNINGS_FRONT_EXPIRATION, "100", OptionType.CALL, "0.55", "2"
        ),
        fixture_contract(
            "ec-back-call-100", EARNINGS_BACK_EXPIRATION, "100", OptionType.CALL, "0.58", "3"
        ),
    )
    return OptionChain(
        "screening-fixture-earnings-chain", fixture_security(), OBSERVED_AT, contracts, EVIDENCE
    )


def earnings_calendar_expirations() -> tuple[ExpirationCycle, ExpirationCycle]:
    front = ExpirationCycle(EARNINGS_FRONT_EXPIRATION, 9, True, False, AS_OF_DATE, EVIDENCE)
    back = ExpirationCycle(EARNINGS_BACK_EXPIRATION, 58, True, False, AS_OF_DATE, EVIDENCE)
    return front, back


def earnings_calendar_event(*, confirmed: bool = True) -> EarningsEvent:
    return EarningsEvent(
        "screening-fixture-earnings-event",
        fixture_security(),
        EARNINGS_EVENT_DATE,
        AnnouncementTime.AFTER_CLOSE,
        Decimal("0.05"),
        confirmed,
        (),
        OBSERVED_AT,
        EVIDENCE,
    )


# --- skew_momentum: no DTE selector node; caller supplies an explicit expiration --

SKEW_EXPIRATION = date(2026, 8, 7)  # +16 days


def skew_momentum_chain() -> OptionChain:
    contracts = (
        fixture_contract("sm-call-100", SKEW_EXPIRATION, "100", OptionType.CALL, "0.55", "2"),
        fixture_contract("sm-call-105", SKEW_EXPIRATION, "105", OptionType.CALL, "0.25", "1"),
    )
    return OptionChain(
        "screening-fixture-skew-chain", fixture_security(), OBSERVED_AT, contracts, EVIDENCE
    )


# --- forward_factor: dte_pair_selector front_min/max=35/90, back_min/max=49/139 ---

FORWARD_FRONT_EXPIRATION = date(2026, 9, 21)  # +61 days
FORWARD_BACK_EXPIRATION = date(2026, 10, 21)  # +91 days


def forward_factor_chain() -> OptionChain:
    # front/back call implied_volatility values are the same known-good pair
    # previously supplied as hardcoded external manifest context (SCREEN-004);
    # they now live on the contracts themselves, where implied_volatility
    # canonically belongs, so ANALYTICS-002's option_implied_volatility feature
    # can extract them directly instead of anything being pre-baked upstream.
    contracts = (
        fixture_contract(
            "ff-front-call",
            FORWARD_FRONT_EXPIRATION,
            "105",
            OptionType.CALL,
            "0.35",
            "2",
            implied_volatility="0.48",
        ),
        fixture_contract(
            "ff-back-call",
            FORWARD_BACK_EXPIRATION,
            "105",
            OptionType.CALL,
            "0.38",
            "3",
            implied_volatility="0.4548992562461861547567860943472296",
        ),
        fixture_contract(
            "ff-front-put", FORWARD_FRONT_EXPIRATION, "95", OptionType.PUT, "-0.35", "2"
        ),
        fixture_contract(
            "ff-back-put", FORWARD_BACK_EXPIRATION, "95", OptionType.PUT, "-0.38", "3"
        ),
    )
    return OptionChain(
        "screening-fixture-forward-chain", fixture_security(), OBSERVED_AT, contracts, EVIDENCE
    )


def forward_factor_expirations() -> ExpirationCollection:
    front = ExpirationCycle(FORWARD_FRONT_EXPIRATION, 61, True, False, AS_OF_DATE, EVIDENCE)
    back = ExpirationCycle(FORWARD_BACK_EXPIRATION, 91, True, False, AS_OF_DATE, EVIDENCE)
    return ExpirationCollection(AS_OF_DATE, (front, back))
