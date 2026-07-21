# Stonk behavioral equivalence

STONK-004 compares the manifest migrations with the read-only legacy Stonk
revision `5f3fec846f70e9739cf3f15695fd587f0604344c`. The revision is provenance for
the regression vectors; ASA neither imports nor executes the legacy package.

| Behavior | Legacy evidence | ASA owner | Classification |
|---|---|---|---|
| Forward implied volatility and factor | `tests/test_forward_factor_service.py` | `ImpliedForwardVolatility`, `ForwardFactor` | Exact equivalence |
| Calendar and double-calendar debit | `tests/test_strategy_structure_builders.py` | structure and debit Components | Exact equivalence |
| Delta-selected vertical strikes and debit | `tests/test_skew_momentum_vertical_service.py` | `VerticalStructure`, `OptionStructureDebit` | Exact equivalence |
| Candidate score boundaries | service tests and strategy modules | `VerdictClassifier` manifest parameters | Exact equivalence |
| Candidate ranking | legacy service-local sorting | ASA Ranking Engine | Intentional refinement |
| Allocation and existing-position checks | legacy service-local portfolio logic | ASA Portfolio Engine | Intentional refinement |
| Numeric values | binary floating point | immutable `Decimal` values | Intentional refinement |
| Time | implicit process time in places | explicit observed/effective time | Intentional refinement |

The forward-factor manifest now computes implied forward volatility from the
front/back volatility and DTE evidence. It no longer accepts a derived strategy
value as external input. Invalid forward variance fails closed.

ASA copied no Stonk ranker and no portfolio allocator. Ranking and portfolio
construction remain in their canonical engines, so migrated manifests cannot
special-case execution or current holdings. Presentation rows, mutable provider
objects, broker topology, and disabled legacy clones are not strategy behavior
and are deliberately excluded.

All equivalence vectors replay twice from identical immutable inputs. Manifest,
component, plugin, graph, ranking, and portfolio identities remain pinned by the
existing deterministic test suites.
