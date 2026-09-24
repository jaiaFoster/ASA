# OUTCOME-INTELLIGENCE-001 — OI-01 immutable opportunity identity

Baseline: `main@7c9bf49`
Sprint start: stable opportunity identities and tracking exist (OP-01, OP-06),
satisfying the program's transition rule; STRATEGY-LIBRARY-001 continues in
parallel (WIP: two workstreams).

## Identity audit

| Required coverage | Where it lives today |
|---|---|
| strategy / version | `OptionTradeProposal.identity` (`strategy`), `TrackedCandidate.strategy_id/strategy_version` |
| subject | `originating_result_identity` (observation id is derived from run, strategy, subject) |
| evidence snapshot | `structure_assessment_identity` → assessment identity includes `evidence_snapshot_identity` |
| exact structure / position | `legs`: canonical contract identity, role, side, quantity |
| modeled entry reference | `entry` and `entry_model` |
| decision time | `TrackedCandidate.originating_observed_at`, `evidence_observed_at`, `tracked_at` |

All are sha256 content identities over canonical JSON; replay of the same
sealed evidence reproduces the same identity (pinned by the OP-01/OP-06 and
strategy replay tests).

## Gap closed: collisions now fail closed

Tracking was idempotent per originating observation via
`ON CONFLICT (originating_observation_id) DO NOTHING`, but a re-track whose
authoritative evidence resolved to a **different** proposal silently returned
the earlier record. `TrackCandidateService.track` now raises
`ProposalIdentityCollisionError` (API `409`) unless the stored identity equals
the recomputed proposal identity — or, for records frozen before OP-06, the
same assessment's identity (the one accepted legacy form).

## Remaining OI work

OI-02–OI-04 add a forward-observation ledger (new immutable persistence), a
material schema change that requires Architect review before implementation.
