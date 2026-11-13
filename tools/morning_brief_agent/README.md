# Morning Brief tooling — no AI API, no separate billing

Stdlib-only Python used by GitHub Actions (deterministic intake) and by the Claude routines
(ledger, claims, selection). All GitHub access is **REST via `gh api`** with explicit pagination and
retry (GraphQL is blocked in Claude sandboxes).

```
python tools/morning_brief_agent/run.py intake [--batch N] [--dry-run]
python tools/morning_brief_agent/run.py status [--json]
python tools/morning_brief_agent/run.py ledger-record --issue N --file rec.json [--dry-run]
python tools/morning_brief_agent/run.py claim acquire|heartbeat|release|status --issue N ...
python tools/morning_brief_agent/run.py candidates
python tools/morning_brief_agent/run.py snapshot --output issues.json
python tools/morning_brief_agent/run.py sync-cursor
```

Modules: `briefs.py` (identity/hash/discovery), `ledger.py` (state machine + record validation),
`claims.py` (crash-safe claims), `selection.py` (eligibility/ranking), `github_api.py` (REST client).
Tests: `python -m pytest tests/tools/morning_brief_agent -q` (run by `Morning Brief Tools CI` and
before every intake). Environment bootstrap for routines: `source tools/morning_brief_agent/routine_env.sh`.

Design: `claude-morning-briefs/WORKER_OWNERSHIP.md`.
