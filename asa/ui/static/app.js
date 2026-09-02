import { api, clearToken, hasToken, setToken } from "./api-client.js";
import { renderApp } from "./render.js";
import {
  exactCounts,
  exactTimestampRange,
  filteredResults,
  routeFromHash,
  state,
} from "./state.js";

const root = document.querySelector("#app");

function model() {
  const route = routeFromHash(location.hash);
  const detailKey = route.name === "detail" ? `${route.signalId}:${route.symbol}` : null;
  const readiness = detailKey ? state.executionReadiness[detailKey] : null;
  const persistedDetail =
    route.name === "detail"
      ? state.results.find(
          (item) => item.signal_id === route.signalId && item.symbol === route.symbol,
        ) || null
      : null;
  return {
    ...state,
    route,
    hasToken: hasToken(),
    visible: filteredResults(),
    detail: persistedDetail && readiness
      ? {
          ...persistedDetail,
          execution_assessment: readiness.execution_assessment,
          modeled_pnl: readiness.modeled_pnl,
        }
      : persistedDetail,
    counts: {
      verdict: exactCounts(state.results, "verdict"),
      evaluation_state: exactCounts(state.results, "evaluation_state"),
      freshness_status: exactCounts(state.results, "freshness_status"),
      usability_status: exactCounts(state.results, "usability_status"),
    },
    evaluatedRange: exactTimestampRange(state.results, "evaluated_at"),
  };
}

async function loadExecutionReadiness() {
  const route = routeFromHash(location.hash);
  if (route.name !== "detail" || !hasToken()) return;
  const key = `${route.signalId}:${route.symbol}`;
  try {
    const response = await api.executionReadiness(route.signalId, route.symbol);
    state.executionReadiness[key] = response.data;
  } catch (error) {
    if (error.status !== 404 && error.status !== 409) throw error;
    delete state.executionReadiness[key];
  }
  render();
}

function render() {
  renderApp(root, model(), handlers);
}

async function loadPersistedState() {
  state.loading = true;
  state.error = null;
  render();
  const infrastructure = await Promise.allSettled([api.health(), api.readiness(), api.version()]);
  if (infrastructure[0].status === "fulfilled") state.health = infrastructure[0].value.data;
  if (infrastructure[1].status === "fulfilled") state.readiness = infrastructure[1].value.data;
  if (infrastructure[2].status === "fulfilled") {
    state.buildIdentity = infrastructure[2].value.data;
    state.apiVersion = infrastructure[2].value.data.api_version;
  }
  if (!hasToken()) {
    state.loading = false;
    render();
    return;
  }
  try {
    const [capabilities, results] = await Promise.all([api.capabilities(), api.results()]);
    state.capabilities = capabilities.data;
    state.results = results.data.results;
    state.apiVersion = results.apiVersion || capabilities.apiVersion;
    state.fetchedAt = new Date().toISOString();
    void loadExecutionReadiness();
  } catch (error) {
    state.error = error.status === 404
      ? "The token is missing, invalid, or the protected API is unavailable."
      : String(error.message || error);
  } finally {
    state.loading = false;
    render();
  }
}

const handlers = {
  connect(token, remember) {
    setToken(token, remember);
    void loadPersistedState();
  },
  clearToken() {
    clearToken();
    state.results = [];
    state.capabilities = null;
    state.error = null;
    render();
  },
  reload() {
    void loadPersistedState();
  },
  filter(key, value) {
    state.filters[key] = value;
    render();
  },
  async modelPnl(item, payload) {
    const key = `${item.signal_id}:${item.symbol}`;
    try {
      const response = await api.modelPnl(item.signal_id, item.symbol, payload);
      state.executionReadiness[key] = {
        ...state.executionReadiness[key],
        modeled_pnl: response.data,
      };
      state.error = null;
    } catch (error) {
      state.error = String(error.message || error);
    }
    render();
  },
};

window.addEventListener("hashchange", () => {
  render();
  void loadExecutionReadiness();
});
if (!location.hash) location.hash = "#/results";
render();
void loadPersistedState();
void loadExecutionReadiness();
setInterval(() => void loadPersistedState(), 60_000);
