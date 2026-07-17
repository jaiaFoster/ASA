# Risk-Scaled Process

Source: RISK-001 §8–§12, ROLE-BOOTSTRAP-01 Founder directions §7–8.

## Risk Classes (RISK-001 §6)

`R0 < R1 < R2 < R3 < R4 < R5`

- **R0** — No material consequence. Typos, comments, whitespace.
- **R1** — Reversible, low-scope. Documentation, minor config, test-only changes.
- **R2** — Technical Change. Schemas, infrastructure, tool changes, POS implementation.
- **R3** — Significant technical risk. Cross-service changes, data migrations, security-adjacent.
- **R4** — Organizational Governance. RoleSpecs, POS requirements, authority changes.
- **R5** — Constitutional. Founding documents, authority hierarchy.

## Process by Class

### R0–R1

**Required:**
- Concise work item (can be a single field in a PR description)
- Implementation
- PR opened on a branch
- Founder merge

**Optional:**
- Tests (proportional to change — trivial fixes may not need new tests)
- Risk record (omit for R0)

### R2

**Required:**
- Work item with objective, scope, and forbidden scope
- Verification commands (what to run to confirm it works)
- Implementation summary in PR or result field
- PR opened on a branch
- Founder merge

**Architect review:** Only if the change materially affects system architecture, interfaces, or canonical data. Routine tooling and POS implementation does not require Architect review.

**Optional:**
- Separate risk record (required if effective class is disputed or manually overridden)
- Separate result record

### R3

**Required:**
- Explicit implementation plan before execution
- Risk notes identifying what could go wrong and how to recover
- Meaningful test coverage for the changed behavior
- Architect review where the change crosses architectural boundaries
- PR with CI passing
- Founder merge

### R4–R5

**Required:**
- Explicit design document (Architect-authored)
- Independent review where possible
- Substantive evidence (test results, audit output, or equivalent)
- Rollback or recovery plan
- Explicit Founder attention before execution or merge
- For R5: constitutional review process

## Founder Direction on Scale

Most ordinary POS and application work will be R1 or R2. Process requirements must scale to actual risk — a routine POS tooling change does not need the same paperwork as a governance document revision.

> The goal is enough process to catch real problems, not enough process to slow everything down.

## Architect Review Trigger

Architect review is required when:

- Architecture changes (system boundaries, interfaces, canonical data model)
- Security or credential handling changes
- A decision will be expensive to reverse
- Multiple implementation approaches differ materially in architectural consequence
- The change creates new coupling between subsystems

Architect review is NOT required for:

- Local reversible changes
- Changes following an existing established pattern
- Documentation-only work
- Narrow bug fixes where the fix is obvious
- Architecture already explicitly decided

## Risk Class Enforcement

- Effective class may never fall below deterministic class (RISK-001 §14)
- Manual override may only raise, never lower
- Override requires explicit authority (recorded in risk record)
