const TOKEN_KEY = "asa-agent-token";

let memoryToken = sessionStorage.getItem(TOKEN_KEY) || "";

export function hasToken() {
  return memoryToken.length > 0;
}

export function setToken(token, rememberForTab = false) {
  memoryToken = String(token || "").trim();
  sessionStorage.removeItem(TOKEN_KEY);
  if (rememberForTab && memoryToken) {
    sessionStorage.setItem(TOKEN_KEY, memoryToken);
  }
}

export function clearToken() {
  memoryToken = "";
  sessionStorage.removeItem(TOKEN_KEY);
}

async function requestJson(path, protectedRoute = true) {
  const headers = { Accept: "application/json" };
  if (protectedRoute && memoryToken) {
    headers.Authorization = `Bearer ${memoryToken}`;
  }
  const response = await fetch(path, {
    method: "GET",
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const error = new Error(`GET ${path} returned HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return { data: await response.json(), apiVersion: response.headers.get("API-Version") };
}

export const api = Object.freeze({
  health: () => requestJson("/api/v1/health", false),
  readiness: () => requestJson("/api/v1/readiness", false),
  version: () => requestJson("/api/v1/version", false),
  capabilities: () => requestJson("/api/v1/capabilities"),
  results: () => requestJson("/api/v1/screening?limit=500&offset=0"),
  result: (signalId, symbol) =>
    requestJson(
      `/api/v1/screening/${encodeURIComponent(signalId)}/${encodeURIComponent(symbol)}`,
    ),
  executionReadiness: (signalId, symbol) =>
    requestJson(
      `/api/v1/screening/${encodeURIComponent(signalId)}/${encodeURIComponent(symbol)}/execution-readiness`,
    ),
  modelPnl: (signalId, symbol, assumptions) =>
    requestJson(
      `/api/v1/screening/${encodeURIComponent(signalId)}/${encodeURIComponent(symbol)}/execution-readiness/modeled-pnl?${new URLSearchParams({
        ...assumptions,
        underlying_price_grid: assumptions.underlying_price_grid.join(","),
        volatility_by_contract: JSON.stringify(assumptions.volatility_by_contract),
      })}`,
    ),
  history: (opportunityId) =>
    requestJson(
      `/api/v1/screening/opportunities/${encodeURIComponent(opportunityId)}/history`,
    ),
});
