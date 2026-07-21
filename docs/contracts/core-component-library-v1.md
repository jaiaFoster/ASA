# Core Component Library v1

The v1 library statically registers Constant, Compare, BooleanAnd, BooleanOr, BooleanNot, Clamp,
Normalize, WeightedScore, Filter, Rank, PortfolioConstraint, and PositionProposal. Each component
has exact typed ports, pinned component and algorithm versions, structured explanation metadata,
no instance state, and one pure evaluation operation. Components contain their bounded financial
transformation; orchestration, ordering, lifecycle, and replay remain owned by Core runtime.
