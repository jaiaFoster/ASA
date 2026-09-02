"""Bounded deterministic front-expiration option P&L model v1."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from domain import OptionLegPosition, OptionType
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)

MODEL_VERSION = "front-expiration-black-scholes-v1"
_PRICE_QUANTUM = Decimal("0.00000001")
_PNL_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ModeledPnLUnknown:
    reason_code: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_code or self.reason_code != self.reason_code.strip():
            raise ValueError("ModeledPnLUnknown.reason_code must be normalized text")


@dataclass(frozen=True, slots=True)
class ModeledPnLAssumptions:
    volatility_by_contract: tuple[tuple[str, Decimal], ...]
    annual_risk_free_rate: Decimal | None
    annual_dividend_yield: Decimal | None
    contract_multiplier: Decimal
    entry_fill_assumption: str = "midpoint"
    expiry_clock_policy: str = "calendar_days_365"

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.volatility_by_contract))
        identities = tuple(identity for identity, _ in normalized)
        if len(identities) != len(set(identities)):
            raise ValueError("volatility assumptions must have unique contract identities")
        if any(not value.is_finite() or value <= 0 for _, value in normalized):
            raise ValueError("volatility assumptions must be positive")
        for value in (self.annual_risk_free_rate, self.annual_dividend_yield):
            if value is not None and not value.is_finite():
                raise ValueError("rate assumptions must be finite")
        if not self.contract_multiplier.is_finite() or self.contract_multiplier <= 0:
            raise ValueError("contract multiplier must be positive")
        if self.entry_fill_assumption != "midpoint":
            raise ValueError("v1 supports midpoint entry only")
        if self.expiry_clock_policy != "calendar_days_365":
            raise ValueError("unsupported expiry clock policy")
        object.__setattr__(self, "volatility_by_contract", normalized)


@dataclass(frozen=True, slots=True)
class ModeledPnLPoint:
    underlying_price: Decimal
    modeled_pnl: Decimal


@dataclass(frozen=True, slots=True)
class ModeledPnLSurface:
    structure_assessment_identity: str
    valuation_model_and_version: str
    valuation_time: datetime
    spot_reference: Decimal
    points: tuple[ModeledPnLPoint, ...]
    entry_fill_assumption: str
    volatility_assumptions: tuple[tuple[str, Decimal], ...]
    annual_risk_free_rate: Decimal
    annual_dividend_yield: Decimal
    contract_multiplier: Decimal

    def __post_init__(self) -> None:
        if self.valuation_time.tzinfo is None:
            raise ValueError("ModeledPnLSurface.valuation_time must be timezone-aware")
        if self.valuation_model_and_version != MODEL_VERSION:
            raise ValueError("unsupported modeled P&L version")
        prices = tuple(item.underlying_price for item in self.points)
        if not prices or tuple(sorted(set(prices))) != prices:
            raise ValueError("ModeledPnLSurface points must be strictly ordered")

    @property
    def identity(self) -> str:
        payload = {
            "assessment": self.structure_assessment_identity,
            "dividend": str(self.annual_dividend_yield),
            "fill": self.entry_fill_assumption,
            "model": self.valuation_model_and_version,
            "multiplier": str(self.contract_multiplier),
            "points": [[str(item.underlying_price), str(item.modeled_pnl)] for item in self.points],
            "rate": str(self.annual_risk_free_rate),
            "spot": str(self.spot_reference),
            "valuation_time": self.valuation_time.isoformat(),
            "volatility": [[key, str(value)] for key, value in self.volatility_assumptions],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def _normal_cdf(value: float) -> float:
    return (1.0 + math.erf(value / math.sqrt(2.0))) / 2.0


def _black_scholes(
    *,
    spot: Decimal,
    strike: Decimal,
    years: Decimal,
    volatility: Decimal,
    rate: Decimal,
    dividend: Decimal,
    option_type: OptionType,
) -> Decimal:
    s, k, t, sigma, r, q = map(float, (spot, strike, years, volatility, rate, dividend))
    root_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    discounted_spot = s * math.exp(-q * t)
    discounted_strike = k * math.exp(-r * t)
    if option_type is OptionType.CALL:
        result = discounted_spot * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
    else:
        result = discounted_strike * _normal_cdf(-d2) - discounted_spot * _normal_cdf(-d1)
    return Decimal(str(result)).quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)


def model_front_expiration_pnl(
    *,
    assessment: ExecutableStructureAssessment,
    valuation_time: datetime,
    spot_reference: Decimal,
    underlying_price_grid: tuple[Decimal, ...],
    assumptions: ModeledPnLAssumptions,
) -> ModeledPnLSurface | ModeledPnLUnknown:
    if assessment.status is not ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
        return ModeledPnLUnknown("structure_not_constructible_as_intended")
    if assessment.modeled_entry_economics is None:
        return ModeledPnLUnknown("midpoint_entry_unavailable")
    if valuation_time.tzinfo is None or valuation_time.tzinfo.utcoffset(valuation_time) is None:
        return ModeledPnLUnknown("valuation_time_not_timezone_aware")
    if (
        not spot_reference.is_finite()
        or spot_reference <= 0
        or not underlying_price_grid
        or any(not item.is_finite() or item <= 0 for item in underlying_price_grid)
    ):
        return ModeledPnLUnknown("invalid_underlying_price_grid")
    if tuple(sorted(set(underlying_price_grid))) != underlying_price_grid:
        return ModeledPnLUnknown("underlying_price_grid_not_strictly_ordered")
    if assumptions.annual_risk_free_rate is None:
        return ModeledPnLUnknown("risk_free_rate_unknown")
    if assumptions.annual_dividend_yield is None:
        return ModeledPnLUnknown("dividend_yield_unknown")

    front_expiration = min(item.leg.contract.expiration for item in assessment.exact_legs)
    if valuation_time.date() != front_expiration:
        return ModeledPnLUnknown("valuation_time_must_be_front_expiration")
    volatility = dict(assumptions.volatility_by_contract)
    later_contracts = tuple(
        item.leg.contract
        for item in assessment.exact_legs
        if item.leg.contract.expiration > front_expiration
    )
    if any(item.identity not in volatility for item in later_contracts):
        return ModeledPnLUnknown("back_leg_volatility_unknown")

    entry = assessment.modeled_entry_economics.modeled_net_debit_or_credit
    points: list[ModeledPnLPoint] = []
    for scenario_spot in underlying_price_grid:
        structure_value = Decimal(0)
        for resolved in assessment.exact_legs:
            contract = resolved.leg.contract
            if contract.expiration == front_expiration:
                if contract.option_type is OptionType.CALL:
                    value = max(Decimal(0), scenario_spot - contract.strike)
                else:
                    value = max(Decimal(0), contract.strike - scenario_spot)
            else:
                remaining_days = (contract.expiration - front_expiration).days
                value = _black_scholes(
                    spot=scenario_spot,
                    strike=contract.strike,
                    years=Decimal(remaining_days) / Decimal(365),
                    volatility=volatility[contract.identity],
                    rate=assumptions.annual_risk_free_rate,
                    dividend=assumptions.annual_dividend_yield,
                    option_type=contract.option_type,
                )
            sign = Decimal(1) if resolved.leg.position is OptionLegPosition.LONG else Decimal(-1)
            structure_value += sign * value * resolved.leg.quantity
        pnl = (structure_value - entry) * assumptions.contract_multiplier
        points.append(ModeledPnLPoint(scenario_spot, pnl.quantize(_PNL_QUANTUM, ROUND_HALF_EVEN)))
    return ModeledPnLSurface(
        assessment.identity,
        MODEL_VERSION,
        valuation_time,
        spot_reference,
        tuple(points),
        assumptions.entry_fill_assumption,
        assumptions.volatility_by_contract,
        assumptions.annual_risk_free_rate,
        assumptions.annual_dividend_yield,
        assumptions.contract_multiplier,
    )
