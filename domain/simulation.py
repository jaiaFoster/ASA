"""Immutable deterministic analytical simulation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.execution import PlannedOrderStatus
from domain.operational import CanonicalInstrumentIdentity, MonetaryAmount
from domain.references import EvidenceReference
from domain.values import DomainInvariantError, require_tz_aware


class SimulationTerminalReason(str, Enum):
    FILLED = "filled"
    DAY_EXPIRED = "day_expired"
    IOC_REMAINDER_CANCELLED = "ioc_remainder_cancelled"
    FOK_NOT_SATISFIED = "fok_not_satisfied"
    GTC_FRAMES_EXHAUSTED = "gtc_frames_exhausted"
    NO_MARKET_FRAME = "no_market_frame"
    NOT_MARKETABLE = "not_marketable"


class SimulationTraceEventType(str, Enum):
    SIMULATION_STARTED = "simulation_started"
    ORDER_EVALUATED = "order_evaluated"
    TRIGGER_EVALUATED = "trigger_evaluated"
    PRICE_EVALUATED = "price_evaluated"
    LIQUIDITY_EVALUATED = "liquidity_evaluated"
    FILL_CREATED = "fill_created"
    ORDER_TERMINATED = "order_terminated"
    SIMULATION_COMPLETED = "simulation_completed"


@dataclass(frozen=True, slots=True)
class SimulationFrame:
    simulation_frame_id: str
    sequence: int
    instrument_identity: CanonicalInstrumentIdentity
    bid: MonetaryAmount
    ask: MonetaryAmount
    last: MonetaryAmount
    available_quantity: Decimal
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if self.sequence <= 0 or self.available_quantity < 0:
            raise DomainInvariantError("SimulationFrame sequence and quantity are invalid")
        if len({self.bid.currency, self.ask.currency, self.last.currency}) != 1:
            raise DomainInvariantError("SimulationFrame currencies must match")
        if min(self.bid.amount, self.ask.amount, self.last.amount) <= 0 or self.bid.amount > self.ask.amount:
            raise DomainInvariantError("SimulationFrame requires positive non-crossed prices")
        if not self.evidence:
            raise DomainInvariantError("SimulationFrame.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class SimulationMarketData:
    simulation_market_data_id: str
    as_of: datetime
    ordered_frames: tuple[SimulationFrame, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        require_tz_aware(self.as_of, "SimulationMarketData", "as_of")
        keys = tuple((frame.instrument_identity, frame.sequence) for frame in self.ordered_frames)
        if len(keys) != len(set(keys)):
            raise DomainInvariantError("Simulation frames must be unique")
        for identity in {frame.instrument_identity for frame in self.ordered_frames}:
            sequences = tuple(frame.sequence for frame in self.ordered_frames if frame.instrument_identity == identity)
            if sequences != tuple(range(1, len(sequences) + 1)):
                raise DomainInvariantError("Simulation frame sequences must be contiguous")
        if not self.evidence:
            raise DomainInvariantError("SimulationMarketData.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    simulated_fill_id: str
    planned_order_id: str
    order_fill_sequence: int
    global_fill_sequence: int
    quantity: Decimal
    price: MonetaryAmount
    frame_sequence: int
    resulting_status: PlannedOrderStatus
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class SimulatedOrderState:
    simulated_order_state_id: str
    simulation_algorithm_version: str
    planned_order_id: str
    status: PlannedOrderStatus
    filled_quantity: Decimal
    remaining_quantity: Decimal
    simulated_fill_ids: tuple[str, ...]
    terminal_reason: SimulationTerminalReason
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if self.filled_quantity < 0 or self.remaining_quantity < 0:
            raise DomainInvariantError("SimulatedOrderState quantities cannot be negative")


@dataclass(frozen=True, slots=True)
class SimulationTraceEvent:
    simulation_trace_event_id: str
    simulation_algorithm_version: str
    sequence: int
    event_type: SimulationTraceEventType
    planned_order_id: str | None
    frame_sequence: int | None
    input_identities: tuple[str, ...]
    output_identities: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class SimulationResult:
    simulation_result_id: str
    simulation_algorithm_version: str
    execution_plan_id: str
    market_data_id: str
    ordered_order_states: tuple[SimulatedOrderState, ...]
    simulated_fills: tuple[SimulatedFill, ...]
    unfilled_quantities: tuple[tuple[str, Decimal], ...]
    trace: tuple[SimulationTraceEvent, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if tuple(event.sequence for event in self.trace) != tuple(range(1, len(self.trace) + 1)):
            raise DomainInvariantError("Simulation trace sequence must be contiguous")
        state_ids = tuple(state.planned_order_id for state in self.ordered_order_states)
        if len(state_ids) != len(set(state_ids)):
            raise DomainInvariantError("SimulationResult requires one state per PlannedOrder")
        if state_ids != tuple(order_id for order_id, _ in self.unfilled_quantities):
            raise DomainInvariantError("Simulation unfilled quantities must follow order states")
        if tuple(fill.global_fill_sequence for fill in self.simulated_fills) != tuple(
            range(1, len(self.simulated_fills) + 1)
        ):
            raise DomainInvariantError("global fill sequence must be contiguous")
        for state in self.ordered_order_states:
            order_fills = tuple(
                fill for fill in self.simulated_fills
                if fill.planned_order_id == state.planned_order_id
            )
            if state.simulated_fill_ids != tuple(fill.simulated_fill_id for fill in order_fills):
                raise DomainInvariantError("order state fill IDs are incoherent")
            if state.filled_quantity != sum((fill.quantity for fill in order_fills), Decimal("0")):
                raise DomainInvariantError("order state filled quantity is incoherent")
