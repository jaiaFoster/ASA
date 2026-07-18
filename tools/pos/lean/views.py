"""
Pure view rendering for the Lean POS generator.

No I/O. No network. Fully deterministic given identical inputs.
Two entry points:
  render_current_state(...)  -> str   (Markdown)
  render_worker_context(...) -> dict  (YAML-serialisable)

Generated output is never canonical. Each call must embed the
non-canonical warning.
"""

from __future__ import annotations

from tools.pos.lean.schemas import (
    LEAN_GENERATED_HEADER,
    TOKEN_BUDGET_CURRENT_STATE,
    TOKEN_BUDGET_WORKER_CONTEXT_NORMAL,
    TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED,
    VALID_RISK_CLASSES,
    estimate_tokens,
)


# ---------------------------------------------------------------------------
# CURRENT_STATE.md
# ---------------------------------------------------------------------------

def render_current_state(
    project_state: dict,
    reconciliation: dict | None,
    trial_rules: list[dict],
    generated_at: str,
    recently_accepted_limit: int = 5,
) -> str:
    """Render CURRENT_STATE.md from canonical + derived inputs."""
    parts: list[str] = [LEAN_GENERATED_HEADER]
    parts.append(f"# Lean POS — Current State\n")
    parts.append(f"**Generated:** {generated_at}  \n")

    repo = (reconciliation or {}).get("repository", "")
    if repo:
        parts.append(f"**Repository:** {repo}  \n")
    parts.append("\n")

    # --- Current Objective ---
    objective = project_state.get("objective", "").strip()
    ps_id = project_state.get("id", "")
    constraints = project_state.get("constraints") or []
    parts.append("## Current Objective\n\n")
    parts.append(f"{objective}  \n")
    if ps_id:
        parts.append(f"*(source: project_state:{ps_id})*\n\n")
    if constraints:
        parts.append("**Active constraints:**\n")
        for c in sorted(constraints):
            parts.append(f"- {c}\n")
        parts.append("\n")

    # --- Active Work (from reconciliation) ---
    derived = (reconciliation or {}).get("derived_state", "undetermined")
    facts = (reconciliation or {}).get("facts", [])
    conflicts = (reconciliation or {}).get("conflicts", [])
    undetermined = (reconciliation or {}).get("undetermined", [])

    if derived in ("active", "review", "planned") and reconciliation:
        parts.append("## Active Work\n\n")
        pr_facts = [f for f in facts if f["code"] in ("F003", "F004", "F005")]
        issue_facts = [f for f in facts if f["code"] == "F001"]
        if pr_facts or issue_facts:
            for f in sorted(issue_facts + pr_facts, key=lambda x: (x["code"], x["source"])):
                parts.append(f"- **{f['source']}**: {f['detail']}\n")
        else:
            parts.append("- State: `" + derived + "`\n")
        parts.append(f"- Derived state: `{derived}`\n")
        if reconciliation:
            obs = reconciliation.get("observed_at", "")
            if obs:
                parts.append(f"- Observed: {obs}\n")
        parts.append("\n")

    # --- Blocked / Conflicted ---
    blocker_facts = [f for f in facts if f["code"] in ("F008", "F010", "F011")]
    if derived == "blocked" and reconciliation:
        parts.append("## Blocked\n\n")
        for f in sorted(blocker_facts, key=lambda x: (x["code"], x["source"])):
            parts.append(f"- [{f['code']}] **{f['source']}**: {f['detail']}\n")
        if not blocker_facts:
            parts.append(f"- Derived state: `blocked`\n")
        parts.append("\n")

    if derived == "conflict" or conflicts:
        parts.append("## Conflicts\n\n")
        for c in sorted(conflicts, key=lambda x: (x["code"], x["source"])):
            parts.append(f"- [{c['code']}] **{c['source']}**: {c['detail']}\n")
        if not conflicts:
            parts.append(f"- Derived state: `conflict` (no conflict detail available)\n")
        parts.append("\n")

    # --- Undetermined ---
    if undetermined:
        parts.append("## Undetermined\n\n")
        for u in sorted(undetermined, key=lambda x: (x["code"], x["source"])):
            parts.append(f"- [{u['code']}] **{u['source']}**: {u['detail']}\n")
        parts.append("\n")

    # --- Recently Accepted ---
    if derived == "accepted" and reconciliation:
        parts.append("## Recently Accepted\n\n")
        merged_facts = [f for f in facts if f["code"] == "F005"]
        for f in merged_facts[:recently_accepted_limit]:
            parts.append(f"- {f['detail']} *(source: {f['source']})*\n")
        parts.append("\n")

    # --- Active Trial Rules ---
    active_rules = [r for r in trial_rules if r.get("state") == "active_trial"]
    if active_rules:
        parts.append("## Active Trial Rules\n\n")
        for r in sorted(active_rules, key=lambda x: x.get("id", "")):
            ref = f" — issue: {r['github_issue']}" if r.get("github_issue") else ""
            parts.append(f"- **{r['id']}**: {r.get('title', '')} [`{r['state']}`]{ref}\n")
        parts.append("\n")

    # --- Unresolved Governance Conflicts ---
    if conflicts:
        parts.append("## Unresolved Governance Conflicts\n\n")
        for c in sorted(conflicts, key=lambda x: (x["code"], x["source"])):
            parts.append(f"- [{c['code']}] {c['detail']} *(source: {c['source']})*\n")
        parts.append("\n")

    # --- Next Action ---
    notes = project_state.get("notes", "").strip()
    if notes:
        parts.append("## Next Action\n\n")
        parts.append(f"{notes}\n\n")

    # --- Sources ---
    parts.append("## Sources\n\n")
    parts.append(f"- project_state: `{ps_id}`\n")
    if reconciliation:
        recon_sources = sorted(reconciliation.get("sources", []))
        for s in recon_sources:
            parts.append(f"- reconciliation: `{s}`\n")
        recon_obs = reconciliation.get("observed_at", "")
        if recon_obs:
            parts.append(f"- observed_at: `{recon_obs}`\n")

    content = "".join(parts)

    # Token budget check
    est = estimate_tokens(content)
    if est > TOKEN_BUDGET_CURRENT_STATE:
        content += (
            f"\n<!-- WARNING: estimated token count ({est}) exceeds budget "
            f"({TOKEN_BUDGET_CURRENT_STATE}). Consider reducing context. -->\n"
        )

    return content


# ---------------------------------------------------------------------------
# WORKER_CONTEXT.yaml
# ---------------------------------------------------------------------------

_EXECUTION_FIELDS = ("id", "goal", "scope", "lock", "accept", "risk", "deliver", "execute", "depends")


def render_worker_context(
    handoff: dict,
    reconciliation: dict | None,
    trial_rules: list[dict],
    generated_at: str,
    repository: str = "",
    base_ref: str = "main",
) -> dict:
    """Render WORKER_CONTEXT.yaml content as a Python dict (YAML-serialisable)."""
    # Embed handoff — only execution-relevant fields, no semantic rewriting
    embedded_handoff: dict = {}
    for key in _EXECUTION_FIELDS:
        if key in handoff:
            embedded_handoff[key] = handoff[key]

    # Risk class → choose token budget
    risk = handoff.get("risk", "R2")
    try:
        risk_rank = list(VALID_RISK_CLASSES)[list(VALID_RISK_CLASSES).index(risk)]
        elevated = risk in ("R3", "R4", "R5")
    except (ValueError, AttributeError):
        elevated = False

    # Relevant trial rules: those relevant to handoff scope/lock
    scope_paths = set(handoff.get("scope") or [])
    lock_paths = set(handoff.get("lock") or [])
    all_paths = scope_paths | lock_paths
    active_rules = [
        {"id": r["id"], "rule": r["rule"], "state": r["state"]}
        for r in sorted(trial_rules, key=lambda x: x.get("id", ""))
        if r.get("state") == "active_trial"
    ]

    # Relevant refs from handoff
    relevant_refs = sorted(handoff.get("refs") or [])

    # Observed GitHub state — compact summary only
    obs_github: dict = {}
    if reconciliation:
        obs_github = {
            "derived_state": reconciliation.get("derived_state", "undetermined"),
            "observed_at": reconciliation.get("observed_at", ""),
        }
        # Summarise blockers
        blocker_facts = [
            f for f in (reconciliation.get("facts") or [])
            if f["code"] in ("F008", "F010", "F011")
        ]
        if blocker_facts:
            obs_github["blockers"] = [
                {"code": f["code"], "source": f["source"], "detail": f["detail"]}
                for f in sorted(blocker_facts, key=lambda x: (x["code"], x["source"]))
            ]
        # Conflicts and undetermined
        if reconciliation.get("conflicts"):
            obs_github["conflicts"] = [
                {"code": c["code"], "source": c["source"], "detail": c["detail"]}
                for c in sorted(reconciliation["conflicts"], key=lambda x: (x["code"], x["source"]))
            ]
        if reconciliation.get("undetermined"):
            obs_github["undetermined"] = [
                {"code": u["code"], "source": u["source"], "detail": u["detail"]}
                for u in sorted(reconciliation["undetermined"], key=lambda x: (x["code"], x["source"]))
            ]
    else:
        obs_github["derived_state"] = "undetermined"
        obs_github["note"] = "No reconciliation data provided"

    # Verification: synthesise from handoff deliver/accept + risk
    verification: list[dict] = []
    for item in handoff.get("accept") or []:
        verification.append({"criterion": item})

    # Stop conditions derived from lock
    stop_conditions: list[str] = [
        "Required change would modify a locked path",
    ]
    for path in sorted(lock_paths)[:3]:  # show up to 3 examples to keep it compact
        stop_conditions.append(f"  locked: {path}")
    stop_conditions.append("Failed generation must not destroy previous output")

    # Sources
    sources: list[dict] = [
        {"type": "handoff", "id": handoff.get("id", "")},
    ]
    if reconciliation:
        recon_sources = sorted(reconciliation.get("sources") or [])
        for s in recon_sources:
            sources.append({"type": "reconciliation", "source": s})

    result = {
        "v": 1,
        "generated_at": generated_at,
        "generated_note": "NOT CANONICAL — do not treat as a canonical record",
        "repository": repository or (reconciliation or {}).get("repository", ""),
        "base_ref": base_ref,
        "handoff": embedded_handoff,
        "relevant_constraints": {
            "risk_class": risk,
            "active_trial_rules": active_rules,
        },
        "relevant_refs": relevant_refs,
        "observed_github_state": obs_github,
        "verification": verification,
        "stop_conditions": stop_conditions,
        "sources": sources,
    }

    return result


def estimate_worker_context_tokens(ctx: dict) -> int:
    import yaml
    text = yaml.dump(ctx, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return estimate_tokens(text)
