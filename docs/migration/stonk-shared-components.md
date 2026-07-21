# STONK-002 — Shared Component Extraction

## Source and boundary

The extraction is based on Stonk revision
`5f3fec846f70e9739cf3f15695fd587f0604344c`, as pinned by STONK-001. Legacy
services and mutable dictionaries were used as behavioral evidence only. The ASA
implementation consumes the immutable financial contracts introduced by ARCH-005 and
does not copy Stonk's providers, service topology, cache, environment configuration,
row schemas, orchestration, or presentation behavior.

All thresholds are explicit Component parameters. All semantic time is supplied through
`EarningsEvent`, `ExpirationCycle`, `ExpirationCollection`, or `OptionChain`; no component
reads the wall clock. Components are stateless and register through the existing static
Plugin SDK.

## Static plugins

| Plugin | Component | Deterministic responsibility |
|---|---|---|
| `asa.stonk.shared` | `required_evidence_gate` | Require an explicit minimum count of unique evidence references |
| `asa.stonk.shared` | `security_universe_filter` | Remove explicitly identified canonical securities without symbol inference |
| `asa.stonk.shared` | `deterministic_security_cap` | Cap the canonically ordered security tuple |
| `asa.stonk.shared` | `weighted_score_with_ceiling` | Compute a non-negative-weighted mean and apply an explicit ceiling |
| `asa.stonk.shared` | `verdict_classifier` | Classify one score into configured PASS, WATCH, or FAIL tiers |
| `asa.stonk.options` | `earnings_event_window` | Test the preferred front-before-event/back-after-event window and confirmation policy |
| `asa.stonk.options` | `expiration_pair_selector` | Select one stable event-spanning pair within explicit DTE bounds |
| `asa.stonk.options` | `dte_pair_selector` | Select one stable front/back pair from explicit DTE, gap, and target policy |
| `asa.stonk.options` | `expiration_pair_projection` | Project one exact pair into typed front and back expiration dates |
| `asa.stonk.options` | `forward_factor` | Calculate source-qualified front IV divided by implied forward IV minus one |
| `asa.stonk.options` | `option_leg_liquidity` | Test observed quote width, open interest, and volume against explicit thresholds |
| `asa.stonk.options` | `delta_nearest_leg` | Select the nearest absolute observed delta with a canonical contract tie-breaker |
| `asa.stonk.options` | `calendar_structure` | Construct a same-strike, front-short/back-long canonical calendar |
| `asa.stonk.options` | `nearest_common_strike_calendar` | Select the common strike nearest an explicit target and construct a calendar |
| `asa.stonk.options` | `vertical_structure` | Construct a distinct-strike, same-expiry delta-selected debit vertical |
| `asa.stonk.options` | `double_calendar_structure` | Compose canonical put and call calendars as a typed tuple |
| `asa.stonk.options` | `option_structure_debit` | Compute mark debit and conservative long-ask/short-bid debit when evidence is complete |

The double calendar is composition of two existing `OptionStructureType.CALENDAR`
values. It does not add a hidden domain structure type. Structure identities hash only
canonical contract observation identities and explicit semantic roles.

## Preserved formulas and deliberate refinements

- Quote spread ratio is `(ask - bid) / mark`. Missing mark, quote, open interest, or
  volume fails the gate; a midpoint is never silently fabricated.
- Delta distance is `abs(abs(observed_delta) - abs(target_delta))`. Equal distances use
  the canonical option-contract ordering, never provider enumeration order.
- Mark debit sums long marks and subtracts short marks. Conservative debit sums long
  asks and subtracts short bids. Missing mandatory leg evidence returns explicit `None`.
- Event calendars prefer the nearest pair enclosing the earnings event. After-close
  earnings on the front expiration date are treated as occurring after that expiry;
  other same-date sessions are not.
- Weighted scoring does not rank Opportunities. It emits one bounded strategy-local
  score for the canonical ASA Guardrail and Ranking pipeline.

## Existing ASA ownership retained

- Stable opportunity ordering remains in the Ranking Engine; no Stonk ranker was copied.
- Portfolio allocation, cash, concentration, diversification, and duplicate exposure
  remain in the Portfolio Engine.
- Position sizing remains in Position Proposal and Portfolio contracts.
- Lifecycle events and execution intent remain in the existing manifest/runtime and
  operational pipeline. No trade-management state machine was introduced.
- Provider normalization remains outside Strategy Components.

## Continuation

STONK-003 may compose these exact component versions into four manifests. Any manifest
that cannot express a required behavior using the frozen financial contracts and this
registered vocabulary is an architecture stop; it must not introduce a runtime special
case or an opaque compatibility mapping.
