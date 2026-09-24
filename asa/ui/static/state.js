export const state = {
  health: null,
  readiness: null,
  buildIdentity: null,
  capabilities: null,
  strategyHealth: null,
  results: [],
  resultsTotal: 0,
  resultsSnapshotIdentity: null,
  retainedNonactiveTotal: 0,
  executionReadiness: {},
  tradeProposals: {},
  terminalPayoffs: {},
  trackedCandidates: {},
  stockProposals: {},
  portfolio: null,
  positions: null,
  apiVersion: null,
  fetchedAt: null,
  loading: false,
  error: null,
  filters: { signal: "", symbol: "", verdict: "", evaluationState: "" },
};

export function filteredResults(source = state.results, filters = state.filters) {
  const symbol = filters.symbol.trim().toUpperCase();
  return source.filter(
    (item) =>
      (!filters.signal || item.signal_id === filters.signal) &&
      (!symbol || String(item.symbol).toUpperCase().includes(symbol)) &&
      (!filters.verdict || item.verdict === filters.verdict) &&
      (!filters.evaluationState || item.evaluation_state === filters.evaluationState),
  );
}

export function exactCounts(source, field) {
  return source.reduce((counts, item) => {
    const key = Object.hasOwn(item, field) ? String(item[field]) : "ABSENT";
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

export function exactTimestampRange(source, field) {
  const values = source
    .filter((item) => Object.hasOwn(item, field) && typeof item[field] === "string")
    .map((item) => item[field])
    .sort();
  if (!values.length) return { earliest: "Unavailable", latest: "Unavailable" };
  return { earliest: values[0], latest: values[values.length - 1] };
}

export function routeFromHash(hash) {
  const route = (hash || "#/results").replace(/^#/, "");
  const parts = route.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "health") return { name: "health" };
  if (parts[0] === "strategies") return { name: "strategies" };
  if (parts[0] === "stocks") {
    return { name: "stocks", subview: parts[1] === "strategies" ? "strategies" : "portfolio" };
  }
  if (parts[0] === "results" && parts.length === 3) {
    return { name: "detail", signalId: parts[1], symbol: parts[2] };
  }
  return { name: "results" };
}

// Asset surfaces follow each strategy's declared contract structure, never its
// identifier: a strategy declaring no option structure is a stock/ETF strategy.
export function isStockSignal(capabilities, signalId) {
  const signal = capabilities?.signals?.find((item) => item.signal_id === signalId);
  return signal?.structure === "none";
}
