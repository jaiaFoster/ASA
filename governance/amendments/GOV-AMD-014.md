# GOV-AMD-014: Analytical Execution Boundary

| Field | Value |
|---|---|
| `amendment_id` | GOV-AMD-014 |
| `status` | Accepted, effective only when this document and its completed review record reach the default branch through Founder merge |
| `proposer` | Founder |
| `date` | 2026-07-21 |
| `risk_class` | R5 — Constitutional |
| `applies_to` | `architecture/CONSTITUTION.md`, Law 5 |
| `binding_scope` | ASA Core analytical-execution authority only |

## Rationale

ASA is an analytical decision platform rather than an operational brokerage platform. Its highest
execution authority is the deterministic generation of immutable Execution Plans. Operational
brokerage actions remain outside ASA Core.

The prior Law 5 used “place orders” broadly enough to make inert order generation and simulation
ambiguous. This amendment distinguishes analytical order artifacts from operational brokerage
mutation without authorizing any live broker communication.

## Constitutional text

Law 5 is replaced with:

> **Analytical execution boundary.** ASA Core SHALL NOT submit, modify, cancel, or otherwise
> mutate brokerage state.
>
> ASA Core SHALL produce immutable Execution Plans representing deterministic portfolio intent.
>
> Execution Plans are analytical artifacts and SHALL NOT have operational side effects.
>
> Any future operational execution capability SHALL exist as a separately governed subsystem
> requiring constitutional amendment and explicit Founder authorization.

## Consequences

ASA Core may perform:

- portfolio analysis
- risk evaluation
- execution planning
- inert order generation
- deterministic replay
- simulation
- explainability
- provenance preservation

ASA Core and every subsystem authorized by this amendment remain prohibited from:

- submitting orders to a broker
- cancelling orders at a broker
- modifying orders at a broker
- authenticating with a broker
- mutating account or brokerage state
- placing live trades

The permission to simulate does not permit an adapter, network client, SDK, credential, session,
provider payload, or callback capable of reaching a live broker. A simulated broker is a pure,
deterministic in-process model over immutable analytical inputs and outputs.

## Conflict and scope analysis

This amendment narrows and clarifies the former read-only law; it does not authorize the live
`submit`, `modify`, `cancel`, or authentication responsibilities originally listed for SPRINT-004
EXEC-006. Those responsibilities remain constitutionally prohibited and must be removed or
replaced by a simulation-only port in the Founder-gated ARCH-006 contract.

The amendment changes no human authority, merge authority, deployment authority, canonical-truth
model, governance role, or risk floor. Founder remains the sole constitutional acceptor. Accepted
GOV-AMD-001 Amendment 013 cannot delegate this amendment's merge.

## Acceptance criteria

- Law 5 contains the exact analytical boundary above.
- Existing inert `ExecutionPlan` and `BrokerRequest` contracts remain analytical artifacts.
- No live broker capability becomes reachable.
- SPRINT-004 cannot treat EXEC-006's original write-capable interface as approved scope.
- Independent, Structural, and Constitutional Reviews are recorded separately.
- POS Validation, frozen-governance integrity, and architecture tests pass.
- Founder merges the amendment PR.

## Reversion path

Reversion requires a Founder-approved R5 amendment restoring or superseding Law 5 after the same
Independent, Structural, and Constitutional Review floor. Reverting this amendment does not
authorize operational execution; it restores the prior absolute read-only wording.

## Founder approval

The Founder explicitly proposed and approved the substance of GOV-AMD-014 on 2026-07-21. The
amendment becomes binding only after required reviews, successful validation, and Founder merge.

## Review records

### Independence record

| Field | Value |
|---|---|
| `review_id` | GOV-AMD-014-ISRCR-001 |
| `reviewer` | `/root/amd013_independent_review` |
| `reviewer_role` | independent structural constitutional reviewer |
| `date` | 2026-07-21 |
| `independence` | Reviewer is neither amendment author nor assigner |

The reviewer inspected this amendment, Constitution Law 5, its regression test, ADR-008,
ADR-009, GOV-AMD-001's lifecycle, RISK-001's R5 floor, RES-001, RES-002, the governance
manifest, and Issue #103.

### Independent Review

**Verdict: Approved with required corrections, satisfied in this revision.** The amendment
selects the simulation-only non-operational resolution of Issue #103, precisely defines existing
inert Execution Plan and Broker Request artifacts, provides explicit rationale and reversion, and
creates no provider, adapter, credential, network, or live brokerage capability.

### Structural Review

**Verdict: Approved after required corrections.** Canonical registration, separate review
records, and strengthened regression coverage were required before validation. This revision
indexes GOV-AMD-014 in GOV-AMD-001, registers both amendment artifacts in
`governance/manifest.yaml`, records the three reviews separately, rejects the former Law 5 text,
and requires the future operational subsystem's explicit Founder authorization.

ADR-008 retains historical broad “read-only” wording. The reviewer classified that wording as a
non-blocking documentation finding because it grants no live capability and ADR-009 plus this
amendment clearly preserve the inert boundary. ARCH-006 should clarify it without changing its
original historical decision.

### Constitutional Review

**Verdict: Approved with activation conditions.** The separately reviewed dimensions are:

- **Human authority — pass:** Founder remains the sole constitutional acceptor and retains
  explicit authority over any future operational subsystem.
- **Fixed authority hierarchy — pass:** no role gains broker, deployment, governance, or
  constitutional authority; Amendment 013 delegation is excluded.
- **Canonical truth model — pass:** evidence, provenance, identity, persistence, and canonical
  state ownership are unchanged.
- **Product boundary — pass:** analytical execution and deterministic simulation become explicit
  while live brokerage remains default-denied.
- **Lower-tier conflicts — conditional pass:** ADR-009 aligns; ADR-008 has stale broad wording but
  no conflicting permission; the incompatible original EXEC-006 scope is rejected.
- **Non-regression — pass subject to validation:** the patch adds no reachable live capability and
  the strengthened regression suite must remain green.

Activation requires successful POS Validation, architecture tests, governance integrity,
repository-required checks, Founder merge, and verification that the merge is present on `main`.
Issue #103 may close only after those conditions are satisfied.
