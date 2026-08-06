"""Strategy execution context (SPRINT-009/EPIC-1, extended by SPRINT-014
S14-PR-05).

What a strategy adapter receives to evaluate one subject. RuntimeContext is
deliberately provider- and fulfillment-free (SPRINT-014 invariant I-09:
strategy-facing code receives no provider, transport, budget, or
fulfillment object) -- ``sealed_evidence`` is the one thing a migrated,
subject-first strategy may read instead: an already-sealed
MarketSnapshot plus already-projected canonical and derived facts
(strategy_runtime.evidence.SubjectSealedEvidence), assembled by the
composition root *before* any strategy runs, never acquired by the
strategy itself. None for a strategy contract that has not been migrated
to the subject-first path yet, or for a caller that never builds it.

EPIC-3's own market_data.CapabilityFulfillmentService (Shared Data
Planning) previously flowed through this context as ``fulfillment`` for
every registered strategy uniformly. SPRINT-014 removed that field: a
strategy not yet migrated to the subject-first path (Forward Factor,
Skew Momentum, as of S14-PR-05) receives its fulfillment service through
an explicitly named, temporary legacy composition binding built directly
into strategy_runtime.adapters.build_migrated_strategy_registry() --
outside RuntimeContext, never as a field here again. See that module's
own docstring for the binding's owner and deletion condition.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_runtime.clock import Clock
from strategy_runtime.contract import StrategyContract
from strategy_runtime.evidence import SubjectSealedEvidence
from strategy_runtime.historical_evidence import HistoricalSkewRepository


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    contract: StrategyContract
    subject: str
    clock: Clock
    run_id: str
    sealed_evidence: SubjectSealedEvidence | None = None
    # SPRINT-013 S13-04D: None for a strategy contract that never consumes
    # historical evidence, or when a caller runs strategies without it at
    # all -- same optionality convention as sealed_evidence above.
    historical_skew_repository: HistoricalSkewRepository | None = None
