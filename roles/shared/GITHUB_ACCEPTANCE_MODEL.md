# GitHub Acceptance Model

Source: ROLE-BOOTSTRAP-01 Founder directions §1–5.

## The Rule

| GitHub Event | POS Meaning |
|--------------|-------------|
| Founder merges PR | Work accepted |
| Authorized sprint delegate merges an eligible PR | Work accepted under the Founder's recorded, bounded delegation |
| Founder requests changes | Work active (changes required) |
| Founder closes PR without merge | Work rejected or cancelled |
| PR open, no action | Pending Founder review |

**A Founder merge is acceptance. A delegated sprint merge is acceptance only
when Accepted GOV-AMD-001 Amendment 013 is active and all of its scope and gate
requirements are evidenced. No separate POS decision record is required for
ordinary merged work.**

## What GitHub Already Stores

GitHub is canonical for:

- PR state (open / merged / closed)
- Who merged and when
- Merge commit SHA
- Head commit SHA at merge
- Code diff
- Review discussion
- CI run status
- Branch name and base branch
- Commit history

The POS must not duplicate this data without clear operational value.

## What the POS Stores Instead

A work record should reference GitHub by:

- PR number
- Branch name
- Base commit (at assignment time)
- Merge commit (after merge, when relevant to post-merge work)

The POS stores information that GitHub cannot: objective, scope, risk class, architecture notes, verification steps, result summary, limitations.

## Acceptance Without Extra Paperwork

When the Founder, or an authorized sprint delegate acting under Amendment 013,
merges an eligible PR:

1. The branch is accepted.
2. The work item status updates to `accepted`.
3. No separate decision record, result record, or evidence record is required unless the risk class demands it.
4. The Manager notes the merge, updates state, and initiates follow-up work.

For R3+ work, additional evidence may be required before the PR is opened — but the merge itself still constitutes acceptance of that evidence.

## Pending State

A PR that is open is pending the applicable merge authority. The Manager should
surface open PRs awaiting action in its regular briefing.

## Exception: Staged Rollout or Protected Deployment

If deployment requires separate Founder authorization (e.g., production release of application code), that authorization is distinct from PR merge. Merge = code accepted. Deploy = code released. The Founder may require a separate step for deploy.
