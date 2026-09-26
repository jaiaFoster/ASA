# Researcher Startup Checklist

Run on every activation. Rehydrate from the repository only.

## 1. Governance
- [ ] Read `governance/amendments/GOV-AMD-017.md`: Part A is your RoleSpec, Part B is delegation.
- [ ] Read `roles/shared/AUTHORITY_BOUNDARIES.md` and `roles/shared/GLOSSARY.md`.
- [ ] Confirm GOV-AMD-017 is on `main` (Founder-merged). If not, you have no role authority. Stop.

## 2. Repository state
- [ ] Run `git fetch origin main` and work from exact current `main`.
- [ ] Run `python tools/pos/lean/research_library.py`. It must print `OK`. If it does not, repair it before anything else.

## 3. Research memory
- [ ] Read `research/README.md` and `research/catalog.yaml`.
- [ ] Note every record's status and `next_research_need`.

## 4. Authority for this session
- [ ] Identify your bounded assignment, or the active research sprint in `docs/sprints/`.
- [ ] If there is a sprint, run `python tools/pos/lean/research_delegation.py docs/sprints/<ID>.yaml`. It must print `OK`.
- [ ] Confirm all of the following. Otherwise you have no merge authority.
  - The sprint file on `main` has `founder_authorized: true` and `status: active`.
  - It reached `main` through a Founder merge. Check with `git log --format='%H %an' -- docs/sprints/<ID>.yaml`.
  - You are the named delegate.
- [ ] Record the activating merge commit for the closure.

## 5. Begin
- [ ] Follow `roles/researcher/OPERATING_LOOP.md`.
