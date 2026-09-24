"""Deterministic terminal payoff for exact same-expiration option legs.

Calendar front-expiration values remain owned by ``modeled_pnl`` because a
later-expiring leg retains model-dependent time value. This module never
pretends that surface is a guaranteed terminal payoff.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

from domain import OptionLegPosition, OptionType
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)

MODEL_VERSION = "exact-leg-terminal-payoff-v1"
_MONEY = Decimal("0.01")


class PayoffQuantityState(StrEnum):
    SUPPORTED = "supported"
    UNBOUNDED = "unbounded"
    UNDEFINED = "undefined"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PayoffQuantity:
    state: PayoffQuantityState
    value: Decimal | None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is PayoffQuantityState.SUPPORTED:
            if self.value is None or self.reason is not None:
                raise ValueError("supported payoff quantity requires only a value")
        elif self.value is not None or not self.reason:
            raise ValueError("non-supported payoff quantity requires only a reason")


@dataclass(frozen=True, slots=True)
class TerminalPayoffPoint:
    underlying_price: Decimal
    payoff: Decimal


@dataclass(frozen=True, slots=True)
class DeterministicTerminalPayoff:
    structure_assessment_identity: str
    model_version: str
    expiration: date
    points: tuple[TerminalPayoffPoint, ...]
    contract_multiplier: Decimal
    entry_fill_assumption: str
    maximum_loss: PayoffQuantity
    maximum_profit: PayoffQuantity
    breakevens: tuple[Decimal, ...]
    semantics: str = "deterministic_terminal_payoff_from_modeled_entry"

    def __post_init__(self) -> None:
        if self.model_version != MODEL_VERSION:
            raise ValueError("unsupported terminal payoff model version")
        if not self.points:
            raise ValueError("terminal payoff requires at least one scenario point")
        prices = tuple(item.underlying_price for item in self.points)
        if tuple(sorted(set(prices))) != prices:
            raise ValueError("terminal payoff points must be strictly ordered")
        if not self.contract_multiplier.is_finite() or self.contract_multiplier <= 0:
            raise ValueError("terminal payoff multiplier must be positive")

    @property
    def identity(self) -> str:
        payload = {
            "assessment": self.structure_assessment_identity,
            "breakevens": [str(value) for value in self.breakevens],
            "entry_fill": self.entry_fill_assumption,
            "expiration": self.expiration.isoformat(),
            "model": self.model_version,
            "multiplier": str(self.contract_multiplier),
            "points": [[str(item.underlying_price), str(item.payoff)] for item in self.points],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class TerminalPayoffUnknown:
    reason_code: str


def model_terminal_payoff(
    *,
    assessment: ExecutableStructureAssessment,
    underlying_price_grid: tuple[Decimal, ...],
    contract_multiplier: Decimal = Decimal("100"),
) -> DeterministicTerminalPayoff | TerminalPayoffUnknown:
    """Model exact-leg expiration payoff when every leg expires together."""
    if assessment.status is not ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
        return TerminalPayoffUnknown("structure_not_constructible_as_intended")
    if assessment.modeled_entry_economics is None:
        return TerminalPayoffUnknown("midpoint_entry_unavailable")
    expirations = {item.leg.contract.expiration for item in assessment.exact_legs}
    if len(expirations) != 1:
        return TerminalPayoffUnknown("multiple_expirations_require_model_dependent_value")
    if (
        not contract_multiplier.is_finite()
        or contract_multiplier <= 0
        or not underlying_price_grid
        or any(not price.is_finite() or price < 0 for price in underlying_price_grid)
        or tuple(sorted(set(underlying_price_grid))) != underlying_price_grid
    ):
        return TerminalPayoffUnknown("invalid_underlying_price_grid")

    entry = assessment.modeled_entry_economics.modeled_net_debit_or_credit

    def payoff(price: Decimal) -> Decimal:
        value = Decimal(0)
        for resolved in assessment.exact_legs:
            contract = resolved.leg.contract
            intrinsic = (
                max(Decimal(0), price - contract.strike)
                if contract.option_type is OptionType.CALL
                else max(Decimal(0), contract.strike - price)
            )
            sign = Decimal(1) if resolved.leg.position is OptionLegPosition.LONG else Decimal(-1)
            value += sign * resolved.leg.quantity * intrinsic
        return ((value - entry) * contract_multiplier).quantize(_MONEY, rounding=ROUND_HALF_EVEN)

    strikes = tuple(sorted({item.leg.contract.strike for item in assessment.exact_legs}))
    extrema_values = tuple(payoff(price) for price in (Decimal(0), *strikes))
    upper_slope = sum(
        (
            (Decimal(1) if item.leg.position is OptionLegPosition.LONG else Decimal(-1))
            * item.leg.quantity
            for item in assessment.exact_legs
            if item.leg.contract.option_type is OptionType.CALL
        ),
        start=Decimal(0),
    )
    maximum_profit = (
        PayoffQuantity(PayoffQuantityState.UNBOUNDED, None, "positive_upper_tail")
        if upper_slope > 0
        else PayoffQuantity(PayoffQuantityState.SUPPORTED, max(Decimal(0), max(extrema_values)))
    )
    maximum_loss = (
        PayoffQuantity(PayoffQuantityState.UNBOUNDED, None, "negative_upper_tail")
        if upper_slope < 0
        else PayoffQuantity(PayoffQuantityState.SUPPORTED, max(Decimal(0), -min(extrema_values)))
    )

    return DeterministicTerminalPayoff(
        assessment.identity,
        MODEL_VERSION,
        next(iter(expirations)),
        tuple(TerminalPayoffPoint(price, payoff(price)) for price in underlying_price_grid),
        contract_multiplier,
        "midpoint_modeled_reference_only",
        maximum_loss,
        maximum_profit,
        _breakevens(payoff, strikes, upper_slope, contract_multiplier),
    )


def default_terminal_payoff_grid(
    assessment: ExecutableStructureAssessment,
) -> tuple[Decimal, ...]:
    """Deterministic display grid derived only from exact canonical strikes."""
    strikes = tuple(sorted({item.leg.contract.strike for item in assessment.exact_legs}))
    if not strikes:
        return ()
    lower = max(Decimal(0), strikes[0] * Decimal("0.80"))
    upper = strikes[-1] * Decimal("1.20")
    step = (upper - lower) / Decimal(20)
    generated = tuple(lower + step * index for index in range(21))
    return tuple(sorted({*generated, *strikes}))


def _breakevens(
    payoff: Callable[[Decimal], Decimal],
    strikes: tuple[Decimal, ...],
    upper_slope: Decimal,
    multiplier: Decimal,
) -> tuple[Decimal, ...]:
    boundaries = (Decimal(0), *strikes)
    roots: set[Decimal] = set()
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        left_value = payoff(left)
        right_value = payoff(right)
        if left_value == 0:
            roots.add(left)
        if right_value == 0:
            roots.add(right)
        if left_value * right_value < 0:
            root = left + (right - left) * (-left_value) / (right_value - left_value)
            roots.add(root.quantize(Decimal("0.00000001"), ROUND_HALF_EVEN))
    last = boundaries[-1]
    last_value = payoff(last)
    tail_slope = upper_slope * multiplier
    if tail_slope != 0:
        root = last - last_value / tail_slope
        if root > last:
            roots.add(root.quantize(Decimal("0.00000001"), ROUND_HALF_EVEN))
    return tuple(sorted(roots))


def terminal_payoff_to_data(
    result: DeterministicTerminalPayoff | TerminalPayoffUnknown,
) -> dict[str, object]:
    if isinstance(result, TerminalPayoffUnknown):
        return {"status": "unknown", "reason_code": result.reason_code}

    def quantity(value: PayoffQuantity) -> dict[str, str | None]:
        return {
            "state": value.state.value,
            "value": None if value.value is None else str(value.value),
            "reason": value.reason,
        }

    return {
        "status": "available",
        "payoff_identity": result.identity,
        "structure_assessment_identity": result.structure_assessment_identity,
        "model_version": result.model_version,
        "expiration": result.expiration.isoformat(),
        "points": [
            {"underlying_price": str(item.underlying_price), "payoff": str(item.payoff)}
            for item in result.points
        ],
        "contract_multiplier": str(result.contract_multiplier),
        "entry_fill_assumption": result.entry_fill_assumption,
        "maximum_loss": quantity(result.maximum_loss),
        "maximum_profit": quantity(result.maximum_profit),
        "breakevens": [str(value) for value in result.breakevens],
        "semantics": result.semantics,
    }
