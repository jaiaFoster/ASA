# STOCK-RUNTIME-001 — STK-05 evidence

## Where "Options"/"Health" tabs actually live

The ticket's premise ("add a Stocks tab alongside Options and Health") maps
to a specific, real surface once located: `asa/ui/static/` — a
framework-free vanilla-JS "Intelligence Console" served as static files by
FastAPI, with its own hash router (`#/results` = the actual Options/
strategy-results view, `#/health` = Runtime health). This is distinct from
`frontend/` (a separate, minimal React app with no tabs at all today — just
a single portfolio dashboard, unrelated to this ticket). All STK-05 work
below is in `asa/ui/static/`.

`asa/ui/static/`'s own automated test suite, `ui-tests/` (Node's built-in
`node:test` + `happy-dom`), is not invoked by any GitHub Actions workflow —
confirmed by grepping every `.github/workflows/*.yml` file. It was run
manually for this change (`cd ui-tests && npm install && npm test`); CI
will not catch a regression here on its own. Flagged as a follow-up, not
fixed in this PR (out of STK-05's own scope).

## What was implemented

A third top-level tab, "Stocks" (`#/stocks`), with two sub-views selected
by an explicit second hash segment:

- `#/stocks/portfolio` (default) — `stockPortfolioView()`: renders
  `GET /api/v1/portfolio`'s already-truthful per-account data (STK-04):
  masked identifier, provider, currency, cash/buying-power/account-value
  (typed `null` shown as an explicit `null`, never blank or fabricated
  zero), and the per-account `holdings_status`/`holdings_as_of` STK-04
  added. An absent publication renders "No published portfolio is
  available." — never an empty-looking table.
- `#/stocks/strategies` — `stockStrategiesView()`: filters the already-
  loaded screening results to `signal_id` in `{B001, B002}` and renders
  benchmark/version, symbol, verdict, direction, price, SMA10M, evaluated
  timestamp, and freshness/usability — reusing the exact same `badge()`/
  `exactValue()`/`resultLink()` helpers the existing Options results table
  already uses, so an absent field (e.g. B001 has no SMA10M metric) reads
  as an explicit `ABSENT`, identical to how every other strategy's gaps
  are already shown.

Generic StructureKind.NONE suppression comes for free, not from a new
branch: clicking into a B001/B002 result reuses the existing, unmodified
`detailView()`, whose execution-readiness section is already gated on
`if (item.execution_assessment)` — B001/B002 simply never populate that
field, so the option-structure/execution-readiness UI is already absent
by construction. No `if (signal_id === "B001")` anywhere in this change.

Supporting plumbing:
- `state.js` — `routeFromHash` parses `#/stocks[/portfolio|/strategies]`;
  `state.portfolio`/`state.positions` added.
- `api-client.js` — `portfolio()`/`positions()` calls added (same
  `requestJson` pattern as every other endpoint).
- `app.js` — `loadPersistedState()` fetches portfolio/positions in
  parallel with (not nested inside) the existing screening fetch, via its
  own `Promise.allSettled`: an absent portfolio (404, no successful broker
  run yet) is a normal, distinguishable state and must never be conflated
  with a broken screening fetch by sharing one try/catch.
- `render.js` — third primary-nav link ("Stocks"); its active-state check
  was rewritten from a fragile `href.includes("health")` string trick to
  an explicit `{href, label, routeName}` list (still functionally
  equivalent for the two existing links, just no longer coincidentally
  correct).
- `styles.css` — `.secondary-nav` (the Portfolio/Stock strategies sub-tabs)
  added; `.primary-nav`'s mobile grid widened from a hard-coded two-column
  layout (which would have silently broken with a third tab) to three;
  badge colors added for the three new `holdings_status` values not
  already covered by an existing wire vocabulary (`success`,
  `success_empty`; `stale_fallback` reuses the existing warning color,
  plain `stale` reuses the existing one).

## A bug found and fixed along the way (shipped separately, PR #420)

Wiring this view surfaced that B001/B002's PASS verdict never actually
produced a visible "BUY" over the API: `asa/api/screening_models.py`'s
top-level `direction` field is derived only from a `"decision.direction"`
metrics key (the same wire-vocabulary key every other migrated strategy's
`explanation_metrics()` populates); STK-03's adapters had set a bare
`"direction"` key instead, which landed in the generic metrics dict but
never the field this UI (and any other API consumer) actually reads.
Fixed and merged ahead of this PR.

## Verification

- `cd ui-tests && npm test`: 13/13 passed (7 pre-existing + 6 new —
  hash-route parsing, nav active-state, strategies-subview row content and
  empty state, portfolio-subview account rendering and empty state).
- `npm run lint` (`node --check` on every touched file): clean.
- Manual smoke test: served `asa/ui/static/` as static files, navigated to
  `#/stocks`, `#/stocks/portfolio`, `#/stocks/strategies` with no token
  (matching real first-load behavior) — confirmed the Stocks nav link,
  sub-nav, and both truthful empty states render correctly; confirmed via
  `document.querySelectorAll` that `active` classes land on the correct
  links for the current route.

## Compatibility

- No backend change. No new endpoint. Existing `#/results` and `#/health`
  routes, their rendering, and all 7 pre-existing `ui-tests` are unchanged
  and still pass.
- No scope beyond the two named sub-views; no broader redesign.

## Follow-up flagged, not actioned here

`ui-tests/` has no CI job. Recommend a follow-up ticket to add an
`asa/ui/static` job to a GitHub Actions workflow (`cd ui-tests && npm ci
&& npm test`) so a future regression here is actually caught.
