"""Generic immutable P09 underlying-exposure plus option-overlay structure."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from domain import Instrument, InstrumentKind, OptionLeg, OptionLegPosition, UnknownReason


class UnderlyingExposureKind(StrEnum):
    INDEX_TOTAL_RETURN = "index_total_return"
    TRADABLE_UNDERLYING = "tradable_underlying"


@dataclass(frozen=True, slots=True)
class UnderlyingExposureLeg:
    """Economic underlying exposure; executability is explicit, never inferred."""

    instrument: Instrument
    quantity: Decimal
    exposure_kind: UnderlyingExposureKind
    broker_executable: bool

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise ValueError("P09 exposure instrument must be canonical")
        if not self.quantity.is_finite() or self.quantity == 0:
            raise ValueError("P09 exposure quantity must be finite and non-zero")
        if self.exposure_kind is UnderlyingExposureKind.INDEX_TOTAL_RETURN:
            if self.instrument.kind is not InstrumentKind.INDEX:
                raise ValueError("index total-return exposure requires an index instrument")
            if self.broker_executable:
                raise ValueError("non-tradable index exposure cannot be broker executable")
        elif self.exposure_kind is UnderlyingExposureKind.TRADABLE_UNDERLYING:
            if self.instrument.kind is InstrumentKind.INDEX:
                raise ValueError("tradable underlying exposure cannot claim an index is tradable")
            if not self.broker_executable:
                raise ValueError("tradable underlying exposure must be broker executable")

    @property
    def identity(self) -> str:
        return _identity(
            "asa.p09.underlying_exposure",
            (
                self.instrument.identity.scheme,
                self.instrument.identity.value,
                self.instrument.kind.value,
                str(self.quantity),
                self.exposure_kind.value,
                self.broker_executable,
            ),
        )


@dataclass(frozen=True, slots=True)
class OptionOverlayPosition:
    """P09 analytical position over one exposure and exact option legs."""

    underlying: UnderlyingExposureLeg
    option_legs: tuple[OptionLeg, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.underlying, UnderlyingExposureLeg):
            raise ValueError("P09 underlying must be an UnderlyingExposureLeg")
        normalized = tuple(sorted(self.option_legs, key=lambda item: item.identity))
        identities = tuple(item.identity for item in normalized)
        if not identities or len(identities) != len(set(identities)):
            raise ValueError("P09 requires unique exact option overlay legs")
        if any(
            item.contract.underlying.instrument != self.underlying.instrument
            for item in normalized
        ):
            raise ValueError("P09 option legs must share the exposure instrument")
        object.__setattr__(self, "option_legs", normalized)

    @property
    def broker_executable(self) -> bool:
        return self.underlying.broker_executable

    @property
    def identity(self) -> str:
        return _identity(
            "asa.p09.option_overlay",
            (self.underlying.identity, tuple(item.identity for item in self.option_legs)),
        )


def overlay_reference_value(
    position: OptionOverlayPosition,
    *,
    underlying_value: Decimal | None,
) -> Decimal | UnknownReason:
    """Analytical marked value; no acquisition and no executability claim."""
    if underlying_value is None:
        return UnknownReason("missing_underlying_exposure_value")
    if not underlying_value.is_finite() or underlying_value <= 0:
        return UnknownReason("invalid_underlying_exposure_value")
    total = position.underlying.quantity * underlying_value
    for leg in position.option_legs:
        contract = leg.contract
        if contract.bid is None or contract.ask is None:
            return UnknownReason("missing_option_overlay_midpoint")
        midpoint = (contract.bid + contract.ask) / Decimal(2)
        sign = Decimal(1) if leg.position is OptionLegPosition.LONG else Decimal(-1)
        total += sign * leg.quantity * midpoint
    return total


def _identity(namespace: str, value: object) -> str:
    return hashlib.sha256(
        json.dumps((namespace, value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
