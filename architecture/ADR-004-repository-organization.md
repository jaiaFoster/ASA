<!-- Repository path: architecture/ADR-004-repository-organization.md -->

# ADR-004: Repository Organization

**Status:** Accepted
**Date:** 2026-07-20

## Context

`ARCHITECTURE_VISION.md` defines the layered intelligence pipeline (External Providers → Observation → Canonical Fact → Derived Indicator → Strategy → Guardrail → Ranking → Presentation) and states that each layer consumes only from the layer(s) below it. `CONSTITUTION.md` Law 3 ("one calculation, one home") and Law 9 ("stable contracts over clever implementations") require that this layering be enforceable, not merely aspirational prose. This ADR translates the Vision's layer diagram into a concrete repository module structure and a binding dependency rule.

This ADR assumes repository organization is ordinarily an Architect-level engineering decision. That assumption is not itself established by anything in this documentation set — no reviewed document defines an Architect/Founder decision-rights model — so it is stated here as an assumption this ADR relies on, not as a settled governance rule (see Open Questions).

## Decision

The repository is organized into one top-level module per pipeline layer, plus one shared module for cross-cutting domain types:

- `providers/` — Provider adapters (ADR-002). Owns all Provider-specific fetching, normalization, and retry logic.
- `observation/` — Observation Layer. Owns Observation storage and identity (ADR-001).
- `reconciliation/` — sits within the Canonical Fact Layer's pipeline position, immediately after `observation/` and before `facts/` (see Revision note, ASA-CORE-003). Owns pure, deterministic Observation-to-Canonical-Fact reconciliation logic — grouping, value resolution, disagreement detection, confidence, and fact identity (ADR-001). No repository access, no I/O.
- `facts/` — Canonical Fact Layer. Owns Canonical Fact storage and versioning orchestration, depending on `reconciliation/` for the reconciliation logic itself (ADR-001).
- `indicators/` — Derived Indicator Layer. Owns shared, reusable indicator calculations, deriving Indicators from Canonical Facts only (ADR-006). Narrower dependency rule (see below, ASA-CORE-004): `indicators/` may depend only on `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`, even though both sit "below" it in the general ordering.
- `strategies/` — Strategy Layer, including a `capabilities/` sub-package for the Capability concept defined in `DOMAIN_GLOSSARY.md`. Owns deterministic Strategy evaluation and Opportunity production (ADR-003). Narrower dependency rule (see below, ASA-CORE-005): `strategies/` may depend only on `strategies/`, `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`, even though both sit "below" it in the general ordering.
- `guardrails/` — Guardrail Layer. Owns platform-wide risk and eligibility rules, shared across all Strategies (Constitution Law 8). Narrower dependency rule (see below, ASA-CORE-006): `guardrails/` may depend only on `guardrails/`, `strategies/`, `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`, even though both sit "below" it in the general ordering.
- `ranking/` — Ranking Layer. Owns ordering of Guardrail-evaluated Opportunities.
- `presentation/` — Presentation Layer. Owns summarization and user-facing output; the only module permitted to invoke a language model.
- `domain/` (shared) — Cross-cutting value types referenced by multiple layers (for example, Confidence and Provenance representations). Exists specifically to satisfy Constitution Law 3: these types are defined once, here, and referenced everywhere, rather than redefined per layer.

**Dependency direction** is strictly one-way and mirrors the Vision's pipeline order:

```
providers → observation → reconciliation → facts → indicators → strategies → guardrails → ranking → presentation
```

Each module may depend on itself, on `domain/`, and on any module strictly below it in this order. No module may depend on a module above it. `presentation/` may be depended on by nothing — it is the terminal layer. This directly operationalizes `ARCHITECTURE_VISION.md`'s Open Question about Ranking-versus-Guardrail dependency direction: Ranking depends on Guardrail output; Guardrail never depends on Ranking.

**`presentation/` is further restricted, and this restriction overrides the general "any module strictly below" rule above:** `presentation/` may depend only on `ranking/` and `domain/`. It may not import `guardrails/`, `strategies/`, `indicators/`, `facts/`, `observation/`, or `providers/`, even though all of them sit "below" it in the general ordering. This is not a relaxation of the general rule but a narrowing of it, made necessary by ADR-003's requirement that the Presentation Layer "never has independent access to raw Observations, Canonical Facts, or Providers" and may only summarize what is already present in the structured Opportunity record it receives from `ranking/`. Without this narrower rule, the general "depend on anything below" permission would allow exactly the direct-Facts access ADR-003 exists to prohibit, and an import-linter built from the general rule alone would not catch it. Any import-boundary tooling built against this ADR must enforce `presentation/`'s narrower allowed-dependency set specifically, not the general rule.

**`indicators/` is likewise narrowed (ASA-CORE-004):** `indicators/` may depend only on `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`, even though both sit "below" it in the general ordering. Rationale mirrors Constitution Law 4 (consumers of established knowledge do not gather it, extended from Strategies to Indicators — ADR-005 already extends this same principle to Guardrails): an Indicator derives from Canonical Facts, which already carry everything an Indicator needs; direct access to raw Observations or Provider adapters would let an Indicator bypass reconciliation's confidence/provenance discipline. Any import-boundary tooling built against this ADR must enforce `indicators/`'s narrower allowed-dependency set specifically, not the general rule.

**`strategies/` is narrowed identically, for the identical reason (ASA-CORE-005):** `strategies/` may depend only on `strategies/`, `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`. Constitution Law 4 ("Strategies consume knowledge, they do not gather it") is the ADR that originally motivated this principle; this narrowing is what makes it structurally enforceable rather than aspirational — a Strategy must evaluate Canonical Facts and Indicators only, never reach past them to raw Observations or Provider adapters. Any import-boundary tooling built against this ADR must enforce `strategies/`'s narrower allowed-dependency set specifically, not the general rule.

**`guardrails/` is narrowed identically, for the identical reason (ASA-CORE-006):** `guardrails/` may depend only on `guardrails/`, `strategies/`, `indicators/`, `facts/`, `reconciliation/`, and `domain/` — not `observation/` or `providers/`. ADR-005 already establishes this principle in prose ("A Guardrail may not read raw Observations directly, for the same reason a Strategy may not"); this narrowing is what makes it structurally enforceable rather than aspirational, exactly as the `indicators/` and `strategies/` narrowings did for their own layers. Any import-boundary tooling built against this ADR must enforce `guardrails/`'s narrower allowed-dependency set specifically, not the general rule.

**Ownership:** each module's architectural boundary — what it is responsible for and what it may depend on — is treated here as an Architect-level engineering decision (see the assumption noted in Context above). Implementation within an already-defined module boundary is a routine engineering task and does not itself require a new ADR.

## Alternatives Considered

1. **No shared `domain/` module; each layer defines its own copies of cross-cutting types like Confidence.** Rejected: directly violates Constitution Law 3 (one calculation, one home) — the same concept would have multiple, potentially divergent implementations across layers.
2. **Organize by feature or vertical slice (e.g., a self-contained module per strategy family, each with its own facts/indicators/strategies).** Rejected: fragments Indicators and Guardrails per feature, leading to duplicate indicator implementations across verticals and undermining Guardrails' platform-wide, shared nature (Constitution Law 8). A new Strategy needing an existing Indicator should reuse it, not reimplement it inside its own vertical.
3. **A single flat module with pipeline stages expressed only as function calls, no package-level boundaries.** Rejected: does not make the dependency direction enforceable at the tooling level — nothing would stop a Strategy from importing a Provider directly, silently undermining provider independence (ADR-002) and the layering the Vision requires.

## Consequences

- Adding a new Provider touches only `providers/` (and, transitively, `observation/` if a new Observation type is introduced) — no other module changes.
- Adding a new Strategy touches `strategies/` and, if a new calculation is needed, `indicators/` — it never touches `providers/` or `facts/`.
- The one-way dependency rule needs some form of enforcement to remain true in practice as the codebase grows (import-linting or equivalent); the specific enforcement mechanism is an engineering/CI concern and is explicitly not decided here (see Open Questions and this document set's stated non-scope).
- The `domain/` module carries a risk of becoming a dumping ground for anything that doesn't obviously belong elsewhere; this ADR does not define a boundary for what belongs in `domain/` beyond "cross-cutting value types referenced by multiple layers," and that boundary may need tightening later.
- Because `presentation/`'s allowed dependencies are narrower than the general rule, any import-linting tool built against this ADR needs at least one per-module exception list, not a single global "N levels down" rule — this is a slightly more complex enforcement target than a pure linear pipeline would be, and is called out explicitly so it isn't lost when enforcement tooling is eventually built (see Open Questions; tooling choice itself remains out of scope here).

## Open Questions

- Whether the one-way dependency rule is enforced via automated tooling (import linting or similar) or via code-review discipline alone is an implementation/engineering decision, intentionally out of scope for this ADR per this documentation set's stated exclusions (no CI implementation details here).
- No convention is fixed here for what may or may not be added to `domain/` beyond the general principle above; if it grows large or unfocused, a follow-up decision may be needed to split it.
- This ADR's Context notes that "repository organization is an Architect-level decision" as an unconfirmed assumption, not an established rule. No document reviewed so far defines who holds decision rights over architecture versus product versus process, or what triggers escalation from one to the other. This should be resolved by a proper governance document, not re-asserted piecemeal in future ADRs.
- `guardrails/` and `indicators/` are given module boundaries here but no structural contract of their own — that is, this ADR says where Guardrail and Indicator code lives, not what a Guardrail or an Indicator structurally is, how either is versioned, or (for Guardrails) whether evaluation is strictly per-Opportunity or can consider a candidate set jointly (e.g., portfolio-level exposure limits comparing multiple Opportunities against each other). The strict one-way pipeline assumed here (`strategies → guardrails → ranking`) implicitly assumes per-Opportunity Guardrail evaluation only; cross-Opportunity Guardrails, if needed, would require a structural change to this pipeline and are not designed here. See ADR-005 and ADR-006, which address the Guardrail and Indicator contracts respectively; ADR-005 additionally flags the cross-Opportunity question explicitly rather than leaving it an unstated assumption.
- `ranking/` similarly has a module boundary here but no contract defining how Opportunities produced by structurally different Strategies are placed on a single common order. That gap is not resolved by this ADR and has no corresponding ADR yet.

## Documentation Impact

`ARCHITECTURE_VISION.md`'s Open Questions section currently asks whether Ranking ever depends on Guardrail output only, or whether the reverse is possible. This ADR settles it: the dependency is strictly one-way, Ranking depends on Guardrail, never the reverse. Recommend removing that Open Question from `ARCHITECTURE_VISION.md` and replacing it with a reference to this ADR.

**Revision note (post-review):** this ADR originally permitted `presentation/` to depend on any module below it, which directly contradicted ADR-003's constraint that the Presentation Layer never has independent access to raw Evidence sources. That contradiction is fixed above by narrowing `presentation/`'s allowed dependencies to `ranking/` and `domain/` only. This ADR also originally asserted a settled Architect/Founder approval hierarchy for repository-organization decisions; that assertion has been walked back to an explicitly flagged assumption, since no other reviewed document establishes such a hierarchy — see Open Questions.

**Revision note (ASA-CORE-003):** this ADR originally assigned reconciliation logic and Canonical Fact versioning to a single `facts/` module. Implementing the reconciliation engine surfaced a reason to split them: reconciliation is a pure, deterministic function of an Observation set (no repository access, fully replayable), while Canonical Fact storage and version-sequence enforcement inherently require repository state. Splitting them keeps `reconciliation/`'s replayability guarantee structurally enforceable (it cannot accidentally acquire a repository dependency) and keeps `facts/`'s storage concerns from leaking into what should be a pure function. `reconciliation/` is added at the Canonical Fact Layer's pipeline position — before `facts/`, which now depends on it — rather than as a new, separately-ranked layer; this is a decomposition of the existing Canonical Fact Layer, not a new pipeline stage.

## References

- `CONSTITUTION.md`, Laws 3, 8, 9, 10
- `ARCHITECTURE_VISION.md`, "Architectural Direction," "Open Questions"
- `DOMAIN_GLOSSARY.md`: Capability, Indicator, Guardrail
- ADR-001, ADR-002, ADR-003, ADR-005, ADR-006
