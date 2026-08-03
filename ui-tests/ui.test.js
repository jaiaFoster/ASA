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

test.after(() => window.close());
