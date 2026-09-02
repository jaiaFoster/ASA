# Executable option mapping v1

The execution-readiness artifact is downstream of, and separate from,
`UniversalScreeningResult`. It consumes the same sealed option evidence; it
does not acquire data or alter strategy verdicts.

| Strategy | Declared intent | Existing exact evidence | v1 resolution constraint |
|---|---|---|---|
| Forward Factor | Calendar | Selected front/back expirations, strikes, canonical `OptionChain` contracts and deltas in read-only knowledge | Preserve selected expirations; construct only same-strike calendars. A diagonal is only alternate evidence. |
| Earnings Calendar | Calendar | Selected front/back contract identities, expirations, target strike and canonical `OptionChain` | Preserve selected pair and require the same canonical strike. |
| Skew Momentum | Vertical | Selected expiration plus canonical ATM/wing call and put contracts, including actual deltas | Preserve expiration and branch; target delta is strategy-declared selection evidence, never inferred by the resolver. |

Canonical `domain.OptionContract` and `domain.OptionLeg` remain the exact-leg
authority. `ExecutableStructureAssessment` adds only execution-readiness
status, originating-result/snapshot identity, selection diagnostics, and an
optional explicitly modeled entry reference. Provider payloads, provider
names, acquisition services, and strategy thresholds are absent.

