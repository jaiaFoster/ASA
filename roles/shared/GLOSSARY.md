# Glossary

Operationally important terms only.

**Founder** — The human owner of ASA 2. Ultimate authority for merging PRs, and sole authority for deploying, creating permanent roles, and constitutional amendments. Merge authority may be delegated only through Accepted GOV-AMD-001 Amendment 013.

**Manager** — The ASA Manager (ROLE-PM). Permanent AI role responsible for delivery coordination: breaking objectives into tickets, assigning workers, summarizing results, surfacing blockers, and keeping project state current. Does not merge, deploy, or accept work.

**Architect** — The ASA System Architect (ROLE-ARCH). Permanent AI role responsible for system design quality: boundaries, interfaces, data models, technical criteria, migration plans. Does not manage the roadmap, merge, or accept work.

**Worker** — A temporary implementation agent. Operates within the bounds of a single assignment. Produces a result record and PR. Has no authority beyond the assignment scope.

**Canonical state** — Information stored in POS records (`project/`) or GitHub (PR metadata, commit history). This is the source of truth. Generated views summarize canonical state but are not themselves canonical.

**Generated view** — A file produced by `tools/pos/generate.py` from canonical records. Not authoritative. Must not be edited manually. Regenerate with `python tools/pos/generate.py`.

**Work item** — A POS record representing a unit of bounded work. Minimum required fields vary by risk class. Contains objective, scope, risk class, and references to execution evidence.

**Acceptance** — A work item is accepted when the Founder merges the associated PR. No separate acceptance record is required for ordinary work.

**Merge** — An action that integrates a branch into `main` and constitutes acceptance of the work. The Founder may merge; a worker may merge only an eligible sprint PR while an Accepted Founder Sprint Delegation is active.

**Risk class** — R0 through R5 (R0 < R1 < R2 < R3 < R4 < R5). Governs how much process a unit of work must pass through. Defined in `governance/frozen/RISK-001`. Not a scheduling priority.

**Bounded scope** — An assignment with explicit `allowed` and `forbidden` path lists. Workers must not touch files outside `allowed` scope or within `forbidden` scope.

**Architecture review** — A review by the Architect of changes that materially affect system boundaries, interfaces, or canonical data. Not required for all PRs — see `roles/shared/RISK_SCALED_PROCESS.md`.

**POS** — Project Operating System. The combination of canonical record files (`project/`), validation tooling (`tools/pos/`), and generator. Stores operational truth. Does not make governance judgments.

**Lean POS v1** — The planned redesign of the current POS prototype. Objective: reduce mandatory record types, eliminate duplicate state, and scale process to actual risk. Design is the Architect's first assignment (ARCH-POS-001).
