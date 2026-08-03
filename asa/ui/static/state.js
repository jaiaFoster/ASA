export const state = {
  health: null,
  readiness: null,
  capabilities: null,
  results: [],
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
  if (parts[0] === "results" && parts.length === 3) {
    return { name: "detail", signalId: parts[1], symbol: parts[2] };
  }
  return { name: "results" };
}
