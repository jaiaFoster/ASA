"""Named, versioned formula definitions for reusable option-strategy facts.

STRATEGY-PRODUCTION-001 SP-01E. Every formula here has one stable id, a
formula version, a unit, a time semantic and a missing-input behavior. The
ids match the research derived-fact registry
(`research/sprints/ASA-RES-STRATEGY-QUALIFICATION-002/derived-fact-registry.yaml`)
so a manifest or explanation can cite exactly one definition.

Formulas return a value or a typed `UnknownReason`. They never coerce a missing
input to zero, PASS or a proxy.
"""

from __future__ import annotations

from dataclasses import dataclass

from analytics.errors import DuplicateFeatureRegistrationError, UnknownFeatureIdError


@dataclass(frozen=True, slots=True)
class FormulaDefinition:
    formula_id: str
    formula_version: str
    unit: str
    time_semantics: str
    missing_behavior: str

    def __post_init__(self) -> None:
        for name in ("formula_id", "formula_version", "unit", "time_semantics", "missing_behavior"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"FormulaDefinition.{name} must be normalized non-empty text")


class FormulaRegistry:
    """Immutable formula_id -> FormulaDefinition catalog; duplicates are rejected."""

    __slots__ = ("_definitions",)

    def __init__(self, definitions: tuple[FormulaDefinition, ...]) -> None:
        registered: dict[str, FormulaDefinition] = {}
        for definition in definitions:
            if definition.formula_id in registered:
                raise DuplicateFeatureRegistrationError(definition.formula_id)
            registered[definition.formula_id] = definition
        self._definitions = registered

    def get(self, formula_id: str) -> FormulaDefinition:
        try:
            return self._definitions[formula_id]
        except KeyError:
            raise UnknownFeatureIdError(formula_id) from None

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))


DF_OPT_MID = "DF-OPT-MID"
DF_OPT_RELATIVE_SPREAD = "DF-OPT-RELATIVE-SPREAD"
DF_OPT_WEIGHTED_SPREAD = "DF-OPT-WEIGHTED-SPREAD"
DF_OPT_EFFECTIVE_PRICE = "DF-OPT-EFFECTIVE-PRICE"
DF_OPT_MONEYNESS_KS = "DF-OPT-MONEYNESS-KS"
DF_OPT_MONEYNESS_SK = "DF-OPT-MONEYNESS-SK"
DF_OPT_DTE_CALENDAR = "DF-OPT-DTE-CALENDAR"
DF_OPT_HOLDING_RETURN = "DF-OPT-HOLDING-RETURN"
DF_DELTA_NEUTRAL_HEDGE_QUANTITY = "DF-DELTA-NEUTRAL-HEDGE-QUANTITY"
DF_STRADDLE_ZERO_DELTA_WEIGHT = "DF-STRADDLE-ZERO-DELTA-WEIGHT"
DF_STRADDLE_RETURN = "DF-STRADDLE-RETURN"
DF_ZERO_COST_OPTION_RETURN = "DF-ZERO-COST-OPTION-RETURN"
DF_CBOE_TBILL_DAILY_ACCRUAL = "DF-CBOE-TBILL-DAILY-ACCRUAL"
DF_XS_QUANTILE_ASSIGNMENT = "DF-XS-QUANTILE-ASSIGNMENT"
DF_TRADING_SESSION_OFFSET = "DF-TRADING-SESSION-OFFSET"
DF_THIRD_FRIDAY_ROLL_DATE = "DF-THIRD-FRIDAY-ROLL-DATE"
DF_FIRST_TRADING_DAY_OF_MONTH = "DF-FIRST-TRADING-DAY-OF-MONTH"
DF_LAST_TRADING_DAY_OF_MONTH = "DF-LAST-TRADING-DAY-OF-MONTH"
DF_MONTHLY_EXPIRATION_DAY = "DF-MONTHLY-EXPIRATION-DAY"
DF_OPTION_TRADE_WINDOW_VWAP = "DF-OPTION-TRADE-WINDOW-VWAP"
DF_GXZ_PAIR_VOLUME = "DF-GXZ-PAIR-VOLUME"
DF_CASH_SECURED_PUT_COLLATERAL = "DF-CASH-SECURED-PUT-COLLATERAL"
DF_CBOE_PUT_CONTRACT_COUNT = "DF-CBOE-PUT-CONTRACT-COUNT"
DF_STRADDLE_MOMENTUM_FORMATION = "DF-STRADDLE-MOMENTUM-FORMATION"

_SNAPSHOT = "one quote snapshot t"
_CALENDAR = "exchange trading calendar, US/Eastern dates"
_UNKNOWN_IF_MISSING = "UNKNOWN if any input is missing"

OPTION_STRATEGY_FORMULAS = FormulaRegistry(
    (
        FormulaDefinition(
            DF_STRADDLE_MOMENTUM_FORMATION,
            "1.0.0",
            "simple monthly return",
            "monthly formation using complete lags 2 through 12; lag 1 skipped",
            "UNKNOWN if any required monthly straddle return is missing",
        ),
        FormulaDefinition(
            DF_OPT_MID,
            "1.0.0",
            "USD per option unit",
            _SNAPSHOT,
            "UNKNOWN if bid or ask is missing",
        ),
        FormulaDefinition(
            DF_OPT_RELATIVE_SPREAD,
            "1.0.0",
            "fraction of midpoint",
            _SNAPSHOT,
            "UNKNOWN if midpoint is missing or zero",
        ),
        FormulaDefinition(
            DF_OPT_WEIGHTED_SPREAD,
            "1.0.0",
            "fraction of weighted midpoint",
            _SNAPSHOT,
            "UNKNOWN if any leg quote is missing or midpoint sum is zero",
        ),
        FormulaDefinition(
            DF_OPT_EFFECTIVE_PRICE,
            "1.0.0",
            "USD per option unit",
            _SNAPSHOT,
            "UNKNOWN if bid or ask is missing",
        ),
        FormulaDefinition(
            DF_OPT_MONEYNESS_KS,
            "1.0.0",
            "dimensionless K/S",
            "underlying price at the option snapshot",
            "UNKNOWN if the underlying price is missing",
        ),
        FormulaDefinition(
            DF_OPT_MONEYNESS_SK,
            "1.0.0",
            "dimensionless S/K",
            "underlying price at the option snapshot",
            "UNKNOWN if the underlying price is missing",
        ),
        FormulaDefinition(
            DF_OPT_DTE_CALENDAR,
            "1.0.0",
            "calendar days",
            "evaluation date in US/Eastern",
            "UNKNOWN if expiration precedes as-of",
        ),
        FormulaDefinition(
            DF_OPT_HOLDING_RETURN,
            "1.0.0",
            "simple return",
            "entry snapshot to exit snapshot or settlement",
            "UNKNOWN if a price is missing or entry price is not positive",
        ),
        FormulaDefinition(
            DF_DELTA_NEUTRAL_HEDGE_QUANTITY,
            "1.0.0",
            "underlying units",
            "formation snapshot, static",
            "UNKNOWN if delta is missing",
        ),
        FormulaDefinition(
            DF_STRADDLE_ZERO_DELTA_WEIGHT,
            "1.0.0",
            "weights summing to one",
            "formation snapshot, not rebalanced",
            "UNKNOWN if an input is missing, delta signs invalid, or a price is not positive",
        ),
        FormulaDefinition(
            DF_STRADDLE_RETURN,
            "1.0.0",
            "simple return",
            "formation to exit",
            "UNKNOWN if either leg return is unknown",
        ),
        FormulaDefinition(
            DF_ZERO_COST_OPTION_RETURN,
            "1.0.0",
            "return per unit premium notional",
            "entry close to exit close or settlement",
            _UNKNOWN_IF_MISSING,
        ),
        FormulaDefinition(
            DF_CBOE_TBILL_DAILY_ACCRUAL,
            "1.0.0",
            "simple return per day step",
            "close to close, calendar days; 28-digit decimal context",
            "UNKNOWN if the Treasury bank-discount rate is unavailable",
        ),
        FormulaDefinition(
            DF_XS_QUANTILE_ASSIGNMENT,
            "1.1.0",
            "integer group 1..Q",
            "formation timestamp",
            "subject excluded when its sort value is unknown; UNKNOWN if the set is empty",
        ),
        FormulaDefinition(
            DF_TRADING_SESSION_OFFSET,
            "1.0.0",
            "trading date",
            _CALENDAR,
            "UNKNOWN if the calendar does not cover the range",
        ),
        FormulaDefinition(
            DF_THIRD_FRIDAY_ROLL_DATE,
            "1.0.0",
            "trading date",
            _CALENDAR,
            "UNKNOWN if the calendar does not cover the month",
        ),
        FormulaDefinition(
            DF_FIRST_TRADING_DAY_OF_MONTH,
            "1.0.0",
            "trading date",
            _CALENDAR,
            "UNKNOWN if the month has no covered trading session",
        ),
        FormulaDefinition(
            DF_LAST_TRADING_DAY_OF_MONTH,
            "1.0.0",
            "trading date",
            _CALENDAR,
            "UNKNOWN if the month has no covered trading session",
        ),
        FormulaDefinition(
            DF_MONTHLY_EXPIRATION_DAY,
            "1.0.0",
            "trading date",
            _CALENDAR,
            "UNKNOWN if the calendar does not cover the month",
        ),
        FormulaDefinition(
            DF_OPTION_TRADE_WINDOW_VWAP,
            "1.0.0",
            "USD per option unit",
            "inclusive event-time window with explicit excluded sale-condition codes",
            "UNKNOWN if the tape is absent or no eligible prints occur in the window",
        ),
        FormulaDefinition(
            DF_GXZ_PAIR_VOLUME,
            "1.0.0",
            "contracts",
            "one exact call-put pair at the entry snapshot",
            "UNKNOWN if either leg volume is unavailable",
        ),
        FormulaDefinition(
            DF_CASH_SECURED_PUT_COLLATERAL,
            "1.0.0",
            "USD collateral present value",
            "formation snapshot through selected put expiration",
            "UNKNOWN if the Treasury collateral return is unavailable or invalid",
        ),
        FormulaDefinition(
            DF_CBOE_PUT_CONTRACT_COUNT,
            "1.0.0",
            "fractional SPX put contracts",
            "monthly PUT roll",
            "UNKNOWN if any sourced capital, settlement, rate, strike or entry input is missing",
        ),
    )
)
