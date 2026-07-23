"""Universal Strategy Runtime (SPRINT-009).

Root-level, deployable-application-independent infrastructure -- a plain
sibling of screening/, market_data/, and domain/, following the same
one-directional dependency rule asa/'s own consolidation established
(ARCH-MONOREPO-001): this package and everything under it may be imported
by asa/, but must never import asa/ itself
(tests/architecture/test_asa_dependency_direction.py enforces this
automatically for every root-level package, this one included).

EPIC-2 (Declarative Strategy Contract) lives in strategy_runtime.contract:
the one shape every strategy declares itself through, and the one thing
the runtime (EPIC-1, added on top of this package as later tickets land)
reads to execute a strategy without a strategy-specific conditional.
"""

from __future__ import annotations

from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.errors import StrategyContractError

__all__ = [
    "NO_LIFECYCLE",
    "DataRequirement",
    "LifecycleDeclaration",
    "LifecycleModel",
    "OutputKind",
    "RequirementCategory",
    "StrategyContract",
    "StrategyContractError",
    "StructureKind",
]
