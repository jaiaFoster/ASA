<!-- Repository path: architecture/CONSTITUTION.md -->

# ASA Constitution

This document contains the architectural laws of ASA. It is deliberately short. A law belongs here only if it is expected to hold for the life of the project, regardless of implementation, provider, or model changes.

This document does not describe how anything is implemented. For implementation decisions, see the ADR corresponding to the relevant law. For long-term direction and philosophy that is not yet a hard law, see `ARCHITECTURE_VISION.md`.

Amending this document should be rare and deliberate.

## The Laws

1. **Facts before opinions.** Raw evidence and interpretation of that evidence are never the same object.

2. **Reality is uncertain.** Every fact ASA holds carries confidence and provenance. Nothing is presented as certain that is not.

3. **One calculation, one home.** A given quantity is computed in exactly one place and consumed everywhere it is needed. It is never independently recomputed by a second component.

4. **Strategies consume knowledge; they do not gather it.** A Strategy operates only on Facts and Indicators already established by lower layers. It does not reach past them to raw provider data.

5. **ASA is a read-only platform.** ASA does not execute trades, place orders, or modify brokerage state, under any circumstance.

6. **Every recommendation must be explainable.** A recommendation that cannot be traced to specific, structured evidence is not made.

7. **Deterministic intelligence.** Everything from Facts through Strategy evaluation is reproducible. Language models operate only in presentation and never influence what is evaluated or recommended.

8. **Guardrails protect users, and guardrails are platform-owned.** Risk and eligibility logic is never duplicated inside individual strategies.

9. **Stable contracts over clever implementations.** An interface, once relied upon by another component, changes deliberately and rarely — not because a better internal implementation was found, but only when the contract itself must change.

10. **Simplicity wins.** Where two designs satisfy the same requirement, the simpler one is chosen, even at the cost of some elegance or performance.

## Open Questions / Requires ADR

- None at this time. If a proposed law is found to conflict with an existing ADR or with `ARCHITECTURE_VISION.md`, that conflict should be raised here rather than silently resolved in either document.
