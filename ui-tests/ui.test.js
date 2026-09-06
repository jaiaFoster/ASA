import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { Window } from "happy-dom";

const fixture = JSON.parse(
  await readFile(new URL("../tests/fixtures/ui-screening-result.json", import.meta.url), "utf8"),
);
const styles = await readFile(
  new URL("../asa/ui/static/styles.css", import.meta.url),
  "utf8",
);

function installDom() {
  const window = new Window({ url: "https://asa.test/ui#/results" });
  globalThis.window = window;
  globalThis.document = window.document;
  globalThis.Option = window.Option;
  return window;
}

const window = installDom();
const { exactValue, renderApp } = await import("../asa/ui/static/render.js");
const { exactCounts, exactTimestampRange, filteredResults, routeFromHash } = await import(
  "../asa/ui/static/state.js"
);

const noOpHandlers = {
  clearToken() {},
  connect() {},
  filter() {},
  reload() {},
};

function model(overrides = {}) {
  return {
    route: { name: "results" },
    hasToken: true,
    health: { status: "ok" },
    readiness: { status: "ready" },
    apiVersion: "v1",
    buildIdentity: { application_version: "0.1.0", api_version: "v1", release_sha: "abc123" },
    results: [fixture],
    visible: [fixture],
    detail: null,
    portfolio: null,
    positions: null,
    fetchedAt: "2026-07-29T13:46:00Z",
    filters: { signal: "", symbol: "", verdict: "", evaluationState: "" },
    loading: false,
    error: null,
    counts: {
      verdict: exactCounts([fixture], "verdict"),
      evaluation_state: exactCounts([fixture], "evaluation_state"),
      freshness_status: exactCounts([fixture], "freshness_status"),
      usability_status: exactCounts([fixture], "usability_status"),
    },
    evaluatedRange: exactTimestampRange([fixture], "evaluated_at"),
    ...overrides,
  };
}

const b001Result = {
  ...fixture,
  signal_id: "B001",
  signal_version: "1.0.0",
  symbol: "SPY",
  outcome: "pass",
  evaluation_state: "pass",
  verdict: "PASS",
  direction: "BUY",
  structure: null,
  lifecycle_stage: null,
  opportunity_id: null,
  opportunity_history_url: null,
  metrics: { price: "560.25" },
  metric_types: { price: "decimal" },
  canonical_facts: {},
  named_derived_facts: {},
  formula_versions: {},
  gate_results: {},
  reason_codes: [],
  assumptions: [],
  blockers: [],
  warnings: [],
};

const b002Result = {
  ...b001Result,
  signal_id: "B002",
  metrics: { price: "560.25", sma_10m_completed_months: "540.10" },
  metric_types: { price: "decimal", sma_10m_completed_months: "decimal" },
};

const portfolioFixture = {
  freshness: { as_of: "2026-09-05T12:00:00Z", status: "fresh", serving_last_success: false },
  data: {
    publication_id: "pub-1",
    snapshot_id: "snap-1",
    provider: "robinhood",
    account_count: 2,
    equity_position_count: 1,
    option_leg_count: 0,
    accounts: [
      {
        id: "acct-1",
        external_account_id: "***********1234",
        provider: "robinhood",
        account_type: "individual",
        display_name: "Individual",
        currency: "USD",
        cash_balance: "1250.00",
        cash_available_for_withdrawal: "1000.00",
        buying_power: "2500.00",
        account_value: "50000.00",
        observed_at: "2026-09-05T12:00:00Z",
        holdings_status: "success",
        holdings_as_of: "2026-09-05T12:00:00Z",
      },
      {
        id: "acct-2",
        external_account_id: "***********5678",
        provider: "robinhood",
        account_type: "roth_ira",
        display_name: "Roth IRA",
        currency: "USD",
        cash_balance: null,
        cash_available_for_withdrawal: null,
        buying_power: null,
        account_value: null,
        observed_at: "2026-09-05T12:00:00Z",
        holdings_status: "success_empty",
        holdings_as_of: "2026-09-05T12:00:00Z",
      },
    ],
  },
};

test("shared public fixture renders exact audit identity, decision, evidence, and time", () => {
  const root = document.createElement("div");
  renderApp(
    root,
    model({ route: { name: "detail" }, detail: fixture }),
    noOpHandlers,
  );

  const text = root.textContent;
  assert.match(text, /skew_momentum \/ AAPL/);
  assert.match(text, /WATCH/);
  assert.match(text, /Evaluation statepass/);
  assert.match(text, /momentum_completeUNKNOWN/);
  assert.match(text, /call_skew_zscore-2.10Formula 1.0.0/);
  assert.match(text, /comparison universe incomplete/);
  assert.match(text, /2026-07-29T13:44:00Z/);
  assert.match(text, /observation:fixture:001/);
});

test("runtime strip renders exact configured build identity and explicit unavailable revision", () => {
  const root = document.createElement("div");
  renderApp(root, model(), noOpHandlers);
  assert.match(root.querySelector(".runtime-strip").textContent, /app:0\.1\.0/);
  assert.match(root.querySelector(".runtime-strip").textContent, /api:v1/);
  assert.match(root.querySelector(".runtime-strip").textContent, /revision:abc123/);

  renderApp(root, model({ buildIdentity: { application_version: "0.1.0", api_version: "v1", release_sha: null } }), noOpHandlers);
  assert.match(root.querySelector(".runtime-strip").textContent, /revision:unavailable/);
});

test("verdict, evaluation state, outcome, UNKNOWN, failures, and stale states stay distinct", () => {
  const root = document.createElement("div");
  const variants = [
    fixture,
    { ...fixture, symbol: "MSFT", verdict: "PASS", outcome: "pass" },
    {
      ...fixture,
      symbol: "MU",
      verdict: "FAIL",
      outcome: "fail",
      evaluation_state: "missing_data",
      freshness_status: "stale",
      usability_status: "rejected",
    },
    { ...fixture, symbol: "GS", verdict: null, outcome: "malformed_output", evaluation_state: "malformed_output" },
    { ...fixture, symbol: "AMD", verdict: null, outcome: "strategy_exception", evaluation_state: "strategy_exception" },
  ];
  renderApp(root, model({ results: variants, visible: variants }), noOpHandlers);

  for (const className of [
    "badge--pass",
    "badge--watch",
    "badge--fail",
    "badge--missing_data",
    "badge--malformed_output",
    "badge--strategy_exception",
    "badge--stale",
    "badge--rejected",
  ]) {
    assert.ok(root.querySelector(`.${className}`), className);
  }
});

test("absent, explicit UNKNOWN, empty list, and empty map are not conflated", () => {
  assert.deepEqual(exactValue({}, "field"), { text: "ABSENT", kind: "absent" });
  assert.deepEqual(exactValue({ field: "UNKNOWN" }, "field"), {
    text: "UNKNOWN",
    kind: "unknown",
  });
  assert.deepEqual(exactValue({ field: [] }, "field"), { text: "Empty list", kind: "empty" });
  assert.deepEqual(exactValue({ field: {} }, "field"), { text: "Empty map", kind: "empty" });
});

test("gate strings remain exact wire strings without boolean coercion", () => {
  const root = document.createElement("div");
  renderApp(root, model({ route: { name: "detail" }, detail: fixture }), noOpHandlers);
  assert.equal(root.querySelector(".badge--true").textContent, "True");
  assert.equal(root.querySelector(".badge--false").textContent, "False");
  assert.equal(root.querySelector(".badge--unknown").textContent, "UNKNOWN");
});

test("selectors are generic and hash routes preserve wire identity", () => {
  assert.equal(filteredResults([fixture], { signal: "skew_momentum", symbol: "aap", verdict: "WATCH", evaluationState: "pass" }).length, 1);
  assert.deepEqual(routeFromHash("#/results/skew_momentum/AAPL"), {
    name: "detail",
    signalId: "skew_momentum",
    symbol: "AAPL",
  });
  assert.deepEqual(exactTimestampRange([fixture], "evaluated_at"), {
    earliest: "2026-07-29T13:44:00Z",
    latest: "2026-07-29T13:44:00Z",
  });
});

test("responsive contract declares desktop table and narrow card modes", () => {
  assert.match(styles, /\.desktop-results/);
  assert.match(styles, /\.mobile-results\s*\{\s*display:\s*none/);
  assert.match(styles, /@media \(max-width: 900px\)/);
  assert.match(styles, /\.desktop-results\s*\{\s*display:\s*none/);
  assert.match(styles, /\.mobile-results\s*\{\s*display:\s*block/);
});

test("stocks hash routes carry an explicit portfolio/strategies subview", () => {
  assert.deepEqual(routeFromHash("#/stocks"), { name: "stocks", subview: "portfolio" });
  assert.deepEqual(routeFromHash("#/stocks/portfolio"), {
    name: "stocks",
    subview: "portfolio",
  });
  assert.deepEqual(routeFromHash("#/stocks/strategies"), {
    name: "stocks",
    subview: "strategies",
  });
});

test("primary nav includes a Stocks link, active only on the stocks route", () => {
  const root = document.createElement("div");
  renderApp(root, model({ route: { name: "stocks", subview: "portfolio" } }), noOpHandlers);
  const links = [...root.querySelectorAll(".primary-nav a")];
  const stocksLink = links.find((link) => link.textContent === "Stocks");
  assert.ok(stocksLink, "expected a Stocks link in the primary nav");
  assert.ok(stocksLink.classList.contains("active"));

  renderApp(root, model({ route: { name: "results" } }), noOpHandlers);
  const stocksLinkOnResults = [...root.querySelectorAll(".primary-nav a")].find(
    (link) => link.textContent === "Stocks",
  );
  assert.ok(!stocksLinkOnResults.classList.contains("active"));
});

test("stock strategies subview renders only B001/B002 rows with truthful BUY direction and SMA10M", () => {
  const root = document.createElement("div");
  renderApp(
    root,
    model({
      route: { name: "stocks", subview: "strategies" },
      results: [fixture, b001Result, b002Result],
    }),
    noOpHandlers,
  );

  const text = root.textContent;
  assert.match(text, /B001 \/ SPY/);
  assert.match(text, /B002 \/ SPY/);
  assert.doesNotMatch(text, /skew_momentum \/ AAPL/);
  // B001 has no SMA10M metric at all -- must read ABSENT, never a fabricated
  // or silently blank cell (this codebase's own exact-value convention).
  const rows = [...root.querySelectorAll(".results-table tbody tr")];
  const b001Row = rows.find((row) => row.textContent.includes("B001"));
  const b002Row = rows.find((row) => row.textContent.includes("B002"));
  assert.match(b001Row.textContent, /BUY/);
  assert.match(b001Row.textContent, /ABSENT/);
  assert.match(b002Row.textContent, /BUY/);
  assert.match(b002Row.textContent, /540\.10/);
});

test("stock strategies subview declares an explicit empty state with no rows", () => {
  const root = document.createElement("div");
  renderApp(
    root,
    model({ route: { name: "stocks", subview: "strategies" }, results: [fixture] }),
    noOpHandlers,
  );
  assert.match(root.textContent, /No persisted stock-benchmark results yet\./);
});

test("stock portfolio subview renders masked identifiers and per-account holdings status", () => {
  const root = document.createElement("div");
  renderApp(
    root,
    model({ route: { name: "stocks", subview: "portfolio" }, portfolio: portfolioFixture }),
    noOpHandlers,
  );

  const text = root.textContent;
  assert.match(text, /Individual/);
  assert.match(text, /\*{11}1234/);
  assert.match(text, /Roth IRA/);
  assert.match(text, /\*{11}5678/);
  assert.ok(root.querySelector(".badge--success"));
  assert.ok(root.querySelector(".badge--success_empty"));
  // A genuinely absent cash balance for the empty account must read as an
  // explicit null, never "0" or a blank cell.
  assert.match(text, /null/);
});

test("stock portfolio subview declares an explicit unavailable state, never a fabricated empty portfolio", () => {
  const root = document.createElement("div");
  renderApp(
    root,
    model({ route: { name: "stocks", subview: "portfolio" }, portfolio: null }),
    noOpHandlers,
  );
  assert.match(root.textContent, /No published portfolio is available\./);
});

test.after(() => window.close());
