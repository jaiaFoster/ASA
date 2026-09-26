# ASA Strategy Research Library

This directory is ASA's canonical durable library for **external strategy evidence**.

It is distinct from `project/research/`, which remains the home of ASA-specific empirical work, preregistrations, data-adequacy studies, forward-outcome studies, and other project-internal research artifacts.

## Purpose

The library answers:

> Which externally researched systematic strategies have credible external evidence sufficient to preserve them as serious candidates for downstream ASA consideration (Amendment 017 A.4), and exactly what does the evidence say about them?

A strategy appearing here is **not** approved for implementation, capital allocation, or production. Research qualification means only that credible external evidence is sufficient to preserve the strategy as a serious candidate for downstream consideration.

The canonical qualification semantics are GOV-AMD-001 Amendment 017 A.4 (`governance/amendments/GOV-AMD-017.md`). `QUALIFIED` does not mean:

- that ASA validated the strategy;
- that ASA should implement it;
- that it outranks another strategy;
- that it is approved for production;
- that it will generate future profits.

Where this README and A.4 differ, A.4 controls. The library is owned by ROLE-RESEARCH. This README is governance-controlled and never changes under delegation.

## Structure

- `catalog.yaml` — canonical research inventory and lifecycle state.
- `strategies/` — one evidence dossier per strategy or strategy family.
- `sources/` — reusable provenance records for external and prior ASA sources.
- `MIGRATION.md` — provenance map from pre-existing ASA research into this library.

## Research lifecycle

Allowed dossier states:

- `DISCOVERED` — candidate identified; evidence quality not assessed.
- `TRIAGE` — preliminary evidence justifies deeper research.
- `DEEP_RESEARCH` — primary sources, replications, contradictions, methodology, practical constraints, and ASA capability mapping are being investigated.
- `QUALIFIED` — credible external evidence is sufficient to preserve the strategy as a serious candidate for downstream ASA consideration (A.4).
- `INSUFFICIENT_EVIDENCE` — interesting, but evidence does not currently justify qualification.
- `REJECTED` — material research findings make additional ASA research resources unwarranted at present.

Statuses describe evidence, not implementation recommendations.

## Evidence classes

Every material claim should identify one of:

- `REPORTED` — directly reported by a cited source.
- `DERIVED` — mechanically derived from cited source information.
- `INFERENCE` — ASA Researcher interpretation.
- `UNKNOWN` — evidence not available.

Source records also identify whether evidence is:

- `EXTERNAL_PRIMARY`
- `EXTERNAL_REPLICATION`
- `EXTERNAL_SECONDARY`
- `ASA_PRIOR_INTERNAL`

ASA prior/internal evidence can inform research context and capability mapping, but it does **not** count as independent external support unless the underlying external source is recovered and evaluated.

## Historical preservation

Existing `project/research/`, `project/reports/`, implementation intake files, and other historical records remain intact. This library references and extends them. It must not erase inconvenient conclusions or rewrite prior research history.

When evidence changes, update the dossier's `updated_at`, preserve the earlier conclusion in its history section, and explain what new evidence changed the status.

## Dossier minimum

A completed research dossier should contain:

1. identity and lifecycle status;
2. concise thesis and proposed mechanism;
3. original research;
4. supporting research and independent replication;
5. failed replication and contradictory research;
6. post-publication evidence;
7. mathematical/signal specification;
8. reported performance with sample, universe, and methodology context;
9. transaction costs, turnover, liquidity, capacity, execution assumptions, regime dependence, and known failure modes;
10. adversarial review;
11. ASA capability mapping;
12. strongest support, strongest contradiction, unresolved questions, limitations, qualification basis;
13. a recoverable source index.

## Research boundary

This library does not authorize ASA backtests, parameter optimization, strategy selection, architecture changes, implementation, deployment, or capital allocation.
