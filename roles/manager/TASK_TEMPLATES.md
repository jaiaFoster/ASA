# Manager Task Templates

Concise templates for common Manager outputs. Adapt to the specific task.

---

## Architect Assignment

```markdown
**Assignment:** ARCH-[ID] — [Title]
**From:** Manager
**Risk class:** R[N]

**Objective:**  
[One sentence: what design or decision is needed]

**Current state:**  
[What exists now; relevant file paths]

**Constraints:**  
[Hard limits, existing decisions, compatibility requirements]

**Questions requiring Architect judgment:**  
1. [Specific design question]
2. ...

**Required output:**  
[Design document / schema / review / recommendation]
Expected path: `[path/to/output.md]`

**Return to:** Manager
**Branch:** [branch-name] (create from main)
```

---

## Implementation Worker Assignment

```markdown
**Assignment:** WORK-[ID] — [Title]
**Risk class:** R[N]
**Base commit:** [SHA]

**Objective:**  
[One concrete deliverable]

**Allowed scope:**
- [path/to/module/]
- [specific/file.py]

**Forbidden scope:**
- governance/frozen/
- [other protected paths]

**Verification:**
```bash
python -m pytest tests/ -v
python tools/pos/validate.py
```
Expected: all tests pass, validator 0 failures.

**Expected result:**  
- PR opened on branch `[branch-name]` from `main`
- Work item updated to `review` status
- Result summary: [what to include]

**Escalate to Manager if:**  
- Scope needs to expand beyond allowed paths
- A design decision is missing and cannot proceed
- Validator or tests were previously failing (don't inherit broken state)
```

---

## Bug-Fix Worker Assignment

```markdown
**Assignment:** FIX-[ID] — [Description]
**Risk class:** R1

**Bug:**  
[Exact symptom and reproduction steps]

**Expected behavior:**  
[What should happen instead]

**Allowed scope:**
- [specific files or paths only]

**Forbidden scope:**
- [everything else — keep this narrow]

**Verification:**
```bash
[test command that demonstrates the fix]
```

**Result:** PR with fix + passing test demonstrating correct behavior.
```

---

## Review Request

```markdown
**Review request:** [Work item or PR ID]
**Reviewer:** [Architect / external]
**PR:** [GitHub link]
**Branch:** [branch-name]

**What to review:**  
[Specific concern or scope of review]

**Not in scope for this review:**  
[Explicit exclusions]

**Required output:**  
[Findings / pass-fail / recommendation]

**Return to:** Manager by [date or milestone]
```

---

## Founder Decision Request

```markdown
**Decision needed:** [Title]
**PR or context:** [Link]

**Facts:**  
[Verified state — brief]

**Options:**  
A. [Option] — [consequence]  
B. [Option] — [consequence]

**Recommendation:** [A / B / other, with one-line rationale]

**Consequence of deferral:** [What blocks if no decision]

**Action:**  
- Approve → [what happens]
- Request changes → [what happens]
```

---

## Result Summary (Manager to Founder)

```markdown
**Work:** [ID] — [Title]
**PR:** [GitHub link]
**Branch:** [branch-name] → `main`

**What changed:**  
[One paragraph: key files, what was implemented]

**Verification:**  
- Tests: [N passed / M failed]
- Validator: [0 failures / N failures]
- CI: [passing / failing / not checked]

**Limitations:**  
[Known gaps, deferred items — be honest]

**Recommendation:** Merge when ready. [Or: changes needed because...]
```

---

## Notes

- Templates are starting points, not rigid forms.
- For R0–R1 work, a worker assignment can be a single short paragraph.
- For R4+ work, expand all sections and require Architect review before issuing.
- Never include the full governance corpus in a worker prompt. Link to files instead.
