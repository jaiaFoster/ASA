# API-005 — AI Agent Validation

Status: Complete.

Sprint reference: SPRINT-008 (`docs/sprints/SPRINT-008.yaml`)
Repository commit at validation time: `c807caf` (`main`)
Validating: `POST /api/v1/screening/{signal}/{symbol}/refresh` (API-004), plus the
read surface it depends on (API-002/API-003).

## 1. Objective

Validate the public Agent Data API using a workflow representative of how a
production AI agent would actually use it: discover what the API offers,
retrieve current screening state, decide from timestamps alone whether any
result needs refreshing, refresh exactly one opportunity, confirm the
result updated, and produce a structured summary from the responses —
never touching the CLI or any internal Python object, only the HTTP surface.

## 2. Validation artifact

`tests/asa/test_ai_agent_workflow.py` implements and continuously enforces
this validation (it runs on every CI build, not just once). It plays the
role of an external HTTP client throughout — the only imports from `asa`
or `screening` anywhere in the file are `build_application`/`Settings`
(to stand up the same composition root a real deployment uses) and
`ScreeningStateRecord`/`InMemoryScreeningStateRepository` (test fixtures
used only to seed *pre-existing* state, exactly as a real Postgres-backed
deployment would already hold overnight-batch results before an agent
ever calls in). No step of the workflow itself calls anything but the
HTTP API.

## 3. Validation flow — step by step

| # | `validation_flow` step | HTTP call | Result |
|---|---|---|---|
| 1 | `discover_capabilities` | `GET /api/v1/capabilities` | Returns all 3 registered signals (`earnings_calendar`, `forward_factor`, `skew_momentum`) with declared `required_capabilities` — no CLI/registry object touched directly. |
| 2 | `retrieve_screening_data` | `GET /api/v1/screening` | Returns the 2 seeded results (one fresh, one 20-hours-stale). |
| 3 | `inspect_timestamps` | (from step 2's response body) | Every result carries `updated_at` and `age_seconds`; both present and non-negative. |
| 4 | `determine_whether_refresh_is_needed` | (agent-side decision, no call) | Applying a simple age threshold (4 hours) to the already-retrieved data identifies exactly one stale pair: `skew_momentum`/`AAPL`. The fresh `forward_factor`/`NVDA` result is correctly left alone. |
| 5 | `refresh_one_opportunity` | `POST /api/v1/screening/skew_momentum/AAPL/refresh` | 200 OK. Exercises `skew_momentum`'s real 3-step live acquisition chain (quote → expirations → option chain) against a scripted transport, and reports `request_count >= 1`. Only the one requested pair is touched — the fresh `forward_factor`/`NVDA` result is untouched. |
| 6 | `retrieve_updated_result` | `GET /api/v1/screening/skew_momentum/AAPL` | `age_seconds` now well under the staleness threshold; `updated_at` has changed from the pre-refresh value. |
| 7 | `generate_structured_morning_brief` | (agent-side synthesis from already-returned JSON) | A small structured object (`opportunity_count`, `refreshed` pairs, and a one-line-per-opportunity `summary` string) is built purely from response fields already returned in steps 2/6 — proving an agent can produce a usable brief from the API alone. |

## 4. Success criteria

| Criterion | How it was checked | Result |
|---|---|---|
| `no_provider_credentials_exposed` | The fake Tradier access token used to drive the scripted refresh (`sandbox-secret-token`) is asserted absent from every one of the 6 HTTP response bodies captured across the whole workflow. | Met |
| `no_cli_dependency` | `tests/asa/test_ai_agent_workflow.py` contains zero imports from `screening.cli`; every workflow step is a `TestClient` HTTP call against `asa.bootstrap.build_application()`, the same composition root the deployed service runs. | Met |
| `deterministic_responses` | An immediate repeat `GET` of the just-refreshed result is asserted identical to the prior response on every field except `age_seconds` (which is allowed to differ by at most 1 second, since real wall-clock time elapses between the two calls). | Met |

## 5. Evidence

```text
PYTHONPATH=. python -m pytest tests/asa/test_ai_agent_workflow.py -q
  1 passed

PYTHONPATH=. python -m pytest tests/ -q --ignore=tests/pos --ignore=tests/deployment_observer
  1717 passed, 17 skipped

PYTHONPATH=. python -m pytest tests/asa/test_boundaries.py -q
  5 passed   (the "strategy"-word ban and single-composition-root checks still hold)

ruff check asa tests/asa
  All checks passed!

mypy asa
  Success: no issues found in 38 source files
```

## 6. Findings

No defects were found in API-002/API-003/API-004 by this validation — the
existing implementation already supports the full agent workflow without
modification. This ticket added no production code (no changes under
`asa/` or `screening/`); its only artifact is the validation test and this
report, matching its own scope as a validation-only ticket.

One clarification surfaced during validation, worth recording for API-006's
documentation: "freshness" and "refresh necessity" are entirely
agent-side policy decisions. The API deliberately exposes only the raw
ingredient (`age_seconds`) and never opinionates about a staleness
threshold — this is intentional (per SPRINT-008's `architecture_principles`)
and should be called out explicitly in the authentication/usage guide so
integrators don't look for a "freshness" field that will never exist.

## 7. Conclusion

All three of API-005's success criteria are met. `docs/sprints/SPRINT-008.yaml`'s
`ai_agent_validation_results` report content is satisfied by this document
plus `tests/asa/test_ai_agent_workflow.py`. Proceeding to API-006
(documentation and deployment).
