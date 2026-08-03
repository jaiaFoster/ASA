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
  return {
    ...state,
    route,
    hasToken: hasToken(),
    visible: filteredResults(),
    detail:
      route.name === "detail"
        ? state.results.find(
            (item) => item.signal_id === route.signalId && item.symbol === route.symbol,
          ) || null
        : null,
    counts: {
      verdict: exactCounts(state.results, "verdict"),
      evaluation_state: exactCounts(state.results, "evaluation_state"),
      freshness_status: exactCounts(state.results, "freshness_status"),
      usability_status: exactCounts(state.results, "usability_status"),
    },
    evaluatedRange: exactTimestampRange(state.results, "evaluated_at"),
  };
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
};

window.addEventListener("hashchange", render);
if (!location.hash) location.hash = "#/results";
render();
void loadPersistedState();
setInterval(() => void loadPersistedState(), 60_000);
