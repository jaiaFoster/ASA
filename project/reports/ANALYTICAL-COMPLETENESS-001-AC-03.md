# ANALYTICAL-COMPLETENESS-001 — AC-03 root-cause repair

## AC02-D01

**Symptom:** CPRT and FDS persisted `subject_preparation_failed` for all three
production strategies (six active identities).

**Reproduction:** Railway logs for the CPRT cohort at
`2026-09-03T17:31:19Z` contain the production stack from
`run_scheduled_refresh` through `run_subject_plan`, `_seal`, and
`seal_subject_snapshot` to:

```text
DomainInvariantError: Observation resolution requires one value per provider
```

A bounded, sanitized reproduction against the production provider configuration
identified the conflicting capability as `earnings_calendar_v1`: Finnhub
returned two `EarningsEvent` observations for the same subject/provider. CPRT's
reported candidate dates were 2026-09-09 and 2026-09-10. No provider payload or
credential was retained.

**Owning layer:** `market_data/fulfillment.py`, the provider-neutral acquisition
quality boundary immediately after adapter output and before fallback/sealing.

**Root cause:** fulfillment validated freshness and field completeness but did
not enforce the resolver's existing one-canonical-value-per-provider-and-subject
contract. Competing same-provider values passed as successful acquisition and
later raised during the shared subject seal. That one optional earnings defect
therefore destroyed otherwise usable Forward Factor and Skew evidence.

**Correction:** fulfillment now rejects competing canonical values for the same
provider/subject as a normalized `schema_mismatch`. Existing audited fallback is
then allowed to proceed. If no provider can supply one unambiguous value, the
capability remains explicitly unavailable; ASA does not choose an earnings date
heuristically.

**Before:** one ambiguous Finnhub response aborted shared preparation and wrote
three generic missing-data results per affected subject.

**After:** the provider attempt is typed and isolated at acquisition. Valid
sibling strategies continue from the same sealed evidence boundary; Earnings
Calendar receives `missing_earnings_date` when no fallback supplies an
unambiguous event. No strategy semantics, provider routing, or acquisition
authority changed.

**Sprint effect:** AC02-D01 is repaired at its owner. Active preparation no
longer converts a competing optional earnings observation into cross-strategy
failure amplification.
