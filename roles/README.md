# ASA Role Operating System

This directory contains operational packages for the two permanent AI roles in ASA 2.

## Roles

| Role | Status | Source Spec | Instructions |
|------|--------|-------------|--------------|
| ASA Manager | Prepared, not instantiated | `governance/frozen/PM-SPEC-v0.2.md` | [manager/INSTRUCTIONS.md](manager/INSTRUCTIONS.md) |
| ASA System Architect | Prepared, not instantiated | `governance/frozen/ARCH-SPEC-v0.2.md` | [architect/INSTRUCTIONS.md](architect/INSTRUCTIONS.md) |

## Quick Links

| Artifact | Path |
|----------|------|
| Manager instantiation prompt | [manager/INSTANTIATION_PROMPT.md](manager/INSTANTIATION_PROMPT.md) |
| Architect instantiation prompt | [architect/INSTANTIATION_PROMPT.md](architect/INSTANTIATION_PROMPT.md) |
| Architect first assignment (ARCH-POS-001) | [architect/FIRST_ASSIGNMENT.md](architect/FIRST_ASSIGNMENT.md) |
| Authority boundaries | [shared/AUTHORITY_BOUNDARIES.md](shared/AUTHORITY_BOUNDARIES.md) |
| GitHub acceptance model | [shared/GITHUB_ACCEPTANCE_MODEL.md](shared/GITHUB_ACCEPTANCE_MODEL.md) |
| Risk-scaled process | [shared/RISK_SCALED_PROCESS.md](shared/RISK_SCALED_PROCESS.md) |
| Founder instantiation guide | [FOUNDER_INSTANTIATION_GUIDE.md](FOUNDER_INSTANTIATION_GUIDE.md) |

## Operating Model

```
Founder (sets direction, holds ultimate merge authority)
   ↓
Manager (coordinates work, issues tickets)
   ↓
Architect (designs systems, reviews architecture)
   ↓
Workers (implement bounded assignments)
```

- Founder merging a PR is acceptance. A merge by a worker is acceptance only
  within an active Founder Sprint Delegation under Accepted Amendment 013.
- Neither Manager nor Architect may merge, deploy, or accept on behalf of the Founder.
- The current POS is provisional scaffolding. The Architect's first task is to design Lean POS v1.

## Governance Notes

- PM-SPEC and ARCH-SPEC are Draft v0.2 — not yet formally accepted through the full review process.
- GOV-AMD-001 Amendment 013 is Accepted; Amendments 001–012 remain Proposed.
- The Founder directions in ROLE-BOOTSTRAP-01 govern where they clarify non-frozen operational assumptions.
