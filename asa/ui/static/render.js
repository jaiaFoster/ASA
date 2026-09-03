function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function option(label, value) {
  const node = element("option", null, label);
  node.value = value;
  return node;
}

function exactValue(object, key) {
  if (!Object.hasOwn(object, key)) return { text: "ABSENT", kind: "absent" };
  const value = object[key];
  if (value === null) return { text: "null", kind: "empty" };
  if (value === "UNKNOWN") return { text: "UNKNOWN", kind: "unknown" };
  if (Array.isArray(value) && value.length === 0) return { text: "Empty list", kind: "empty" };
  if (typeof value === "object" && Object.keys(value).length === 0) {
    return { text: "Empty map", kind: "empty" };
  }
  return { text: String(value), kind: "value" };
}

function badge(value, family = "state") {
  const resolved = value === null || value === undefined ? "ABSENT" : String(value);
  const node = element("span", `badge badge--${family} badge--${resolved.toLowerCase()}`, resolved);
  return node;
}

function definitionList(entries) {
  const list = element("dl", "definition-list");
  for (const [label, value, kind] of entries) {
    list.append(element("dt", null, label));
    const detail = element("dd", kind ? `value--${kind}` : null);
    detail.textContent = value;
    list.append(detail);
  }
  return list;
}

function objectSection(title, values, formulaVersions = null) {
  const section = element("section", "audit-section");
  section.append(element("h3", null, title));
  const entries = Object.entries(values || {});
  if (!entries.length) {
    section.append(element("p", "empty-state", "No values emitted"));
    return section;
  }
  const grid = element("div", "fact-grid");
  for (const [key, value] of entries) {
    const card = element("article", "fact-card");
    card.append(element("h4", null, key));
    const raw = exactValue({ value }, "value");
    card.append(element("code", `value--${raw.kind}`, raw.text));
    if (formulaVersions && Object.hasOwn(formulaVersions, key)) {
      card.append(element("small", null, `Formula ${formulaVersions[key]}`));
    }
    grid.append(card);
  }
  section.append(grid);
  return section;
}

function gateSection(gates) {
  const section = element("section", "audit-section");
  section.append(element("h3", null, "Gate results"));
  const entries = Object.entries(gates || {});
  if (!entries.length) {
    section.append(element("p", "empty-state", "No gates emitted"));
    return section;
  }
  const grid = element("div", "gate-grid");
  for (const [key, value] of entries) {
    const item = element("div", "gate-row");
    item.append(element("span", null, key));
    const raw = String(value);
    const kind = raw === "True" ? "pass" : raw === "False" ? "fail" : raw === "UNKNOWN" ? "unknown" : "raw";
    item.append(badge(raw, kind));
    grid.append(item);
  }
  section.append(grid);
  return section;
}

function shellHeader(model, handlers) {
  const header = element("header", "masthead");
  const brand = element("div", "brand-block");
  brand.append(element("p", "eyebrow", "ASA / ANALYTICAL SYSTEM"));
  brand.append(element("h1", null, "Intelligence Console"));
  brand.append(element("p", "brand-subtitle", "Persisted evidence. Exact decisions. No execution."));
  header.append(brand);

  const status = element("div", "runtime-strip");
  const health = model.health?.status || (model.health ? "available" : "unknown");
  const readiness = model.readiness?.status || (model.readiness ? "ready" : "unknown");
  status.append(badge(`health:${health}`, health === "ok" ? "pass" : "unknown"));
  status.append(badge(`readiness:${readiness}`, readiness === "ready" ? "pass" : "unknown"));
  status.append(badge(`app:${model.buildIdentity?.application_version || "unavailable"}`, "raw"));
  status.append(badge(`api:${model.apiVersion || "unavailable"}`, "raw"));
  status.append(badge(`revision:${model.buildIdentity?.release_sha || "unavailable"}`, "raw"));
  header.append(status);

  const nav = element("nav", "primary-nav");
  nav.setAttribute("aria-label", "Primary navigation");
  for (const [href, label] of [["#/results", "Latest results"], ["#/health", "Runtime health"]]) {
    const link = element("a", model.route.name === (href.includes("health") ? "health" : "results") ? "active" : "", label);
    link.href = href;
    nav.append(link);
  }
  const reload = element("button", "button button--quiet", "Reload persisted results");
  reload.type = "button";
  reload.addEventListener("click", handlers.reload);
  nav.append(reload);
  header.append(nav);
  return header;
}

function connectionPanel(handlers, hasToken) {
  const panel = element("section", "connection-panel");
  panel.setAttribute("aria-labelledby", "connection-title");
  panel.append(element("h2", null, hasToken ? "API connected" : "Connect to the Agent Data API"));
  if (hasToken) {
    panel.append(element("p", null, "Bearer token is held outside the rendered page."));
    const clear = element("button", "button button--quiet", "Forget token");
    clear.type = "button";
    clear.addEventListener("click", handlers.clearToken);
    panel.append(clear);
    return panel;
  }
  const form = element("form", "token-form");
  const label = element("label", null, "Existing agent bearer token");
  label.htmlFor = "agent-token";
  const input = element("input");
  input.id = "agent-token";
  input.name = "agent-token";
  input.type = "password";
  input.autocomplete = "off";
  input.required = true;
  const rememberLabel = element("label", "remember-label");
  const remember = element("input");
  remember.type = "checkbox";
  remember.name = "remember-tab";
  rememberLabel.append(remember, document.createTextNode(" Remember for this tab"));
  const submit = element("button", "button button--primary", "Connect read-only");
  submit.type = "submit";
  form.append(label, input, rememberLabel, submit);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const token = input.value;
    input.value = "";
    handlers.connect(token, remember.checked);
  });
  panel.append(form);
  return panel;
}

function resultLink(item) {
  const link = element("a", "result-link", `${item.signal_id} / ${item.symbol}`);
  link.href = `#/results/${encodeURIComponent(item.signal_id)}/${encodeURIComponent(item.symbol)}`;
  return link;
}

function resultsView(model, handlers) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "LATEST PERSISTED SNAPSHOT"));
  heading.append(element("h2", null, "Strategy results"));
  heading.append(element("p", null, "Rows may span refresh times; the API exposes no cycle identifier."));
  fragment.append(heading);

  const summary = element("section", "summary-grid");
  const summaries = [
    ["Visible rows", String(model.visible.length)],
    ["Persisted rows", String(model.results.length)],
    ["Last fetched", model.fetchedAt || "Not fetched"],
    ["Revision", "Unavailable from API"],
  ];
  for (const [label, value] of summaries) {
    const card = element("article", "summary-card");
    card.append(element("span", null, label), element("strong", null, value));
    summary.append(card);
  }
  fragment.append(summary);

  const filters = element("form", "filter-bar");
  filters.setAttribute("aria-label", "Result filters");
  const filterDefinitions = [
    ["signal", "Signal", [...new Set(model.results.map((item) => item.signal_id))].sort()],
    ["verdict", "Verdict", [...new Set(model.results.map((item) => item.verdict).filter((item) => item !== null))].sort()],
    ["evaluationState", "Evaluation state", [...new Set(model.results.map((item) => item.evaluation_state))].sort()],
  ];
  for (const [key, labelText, values] of filterDefinitions) {
    const label = element("label", null, labelText);
    const select = element("select");
    select.name = key;
    select.append(option("All", ""));
    for (const value of values) select.append(option(value, value));
    select.value = model.filters[key];
    select.addEventListener("change", () => handlers.filter(key, select.value));
    label.append(select);
    filters.append(label);
  }
  const symbolLabel = element("label", null, "Symbol contains");
  const symbol = element("input");
  symbol.name = "symbol";
  symbol.value = model.filters.symbol;
  symbol.addEventListener("input", () => handlers.filter("symbol", symbol.value));
  symbolLabel.append(symbol);
  filters.append(symbolLabel);
  fragment.append(filters);

  const tableWrap = element("div", "table-wrap desktop-results");
  const table = element("table", "results-table");
  const head = element("thead");
  const headRow = element("tr");
  for (const title of ["Identity", "Verdict", "Evaluation", "Outcome", "Direction", "Lifecycle", "Freshness", "Usability", "Evaluated", "Issues"]) {
    headRow.append(element("th", null, title));
  }
  head.append(headRow);
  table.append(head);
  const body = element("tbody");
  for (const item of model.visible) {
    const row = element("tr");
    const identity = element("td");
    identity.append(resultLink(item), element("small", null, `v${item.signal_version}`));
    row.append(identity);
    const verdict = element("td"); verdict.append(badge(item.verdict, "verdict")); row.append(verdict);
    const evaluation = element("td"); evaluation.append(badge(item.evaluation_state, "evaluation")); row.append(evaluation);
    row.append(element("td", null, String(item.outcome)));
    row.append(element("td", null, exactValue(item, "direction").text));
    row.append(element("td", null, exactValue(item, "lifecycle_stage").text));
    const freshness = element("td"); freshness.append(badge(item.freshness_status, "freshness")); row.append(freshness);
    const usability = element("td"); usability.append(badge(item.usability_status, "usability")); row.append(usability);
    row.append(element("td", "timestamp", String(item.evaluated_at)));
    row.append(element("td", null, `${item.blockers?.length || 0} blockers / ${item.warnings?.length || 0} warnings`));
    body.append(row);
  }
  table.append(body);
  tableWrap.append(table);
  fragment.append(tableWrap);

  const cards = element("div", "mobile-results");
  for (const item of model.visible) {
    const card = element("article", "result-card");
    card.append(resultLink(item));
    const states = element("div", "badge-row");
    states.append(badge(item.verdict, "verdict"), badge(item.evaluation_state, "evaluation"), badge(item.freshness_status, "freshness"));
    card.append(states);
    card.append(definitionList([
      ["Outcome", String(item.outcome)],
      ["Direction", exactValue(item, "direction").text, exactValue(item, "direction").kind],
      ["Usability", String(item.usability_status)],
      ["Evaluated", String(item.evaluated_at)],
    ]));
    cards.append(card);
  }
  fragment.append(cards);

  if (!model.visible.length) fragment.append(element("p", "empty-state empty-state--large", "No persisted results match these exact filters."));
  return fragment;
}

function detailView(item, handlers) {
  const fragment = document.createDocumentFragment();
  const back = element("a", "back-link", "← Latest results"); back.href = "#/results"; fragment.append(back);
  const heading = element("section", "page-heading detail-heading");
  heading.append(element("p", "eyebrow", "RESULT AUDIT"));
  heading.append(element("h2", null, `${item.signal_id} / ${item.symbol}`));
  const states = element("div", "badge-row badge-row--large");
  states.append(badge(item.verdict, "verdict"), badge(item.evaluation_state, "evaluation"), badge(item.outcome, "state"));
  heading.append(states);
  fragment.append(heading);

  const decision = element("section", "audit-section audit-section--lead");
  decision.append(element("h3", null, "Decision semantics"));
  decision.append(definitionList([
    ["Signal version", exactValue(item, "signal_version").text],
    ["Verdict", exactValue(item, "verdict").text, exactValue(item, "verdict").kind],
    ["Evaluation state", exactValue(item, "evaluation_state").text],
    ["Outcome", exactValue(item, "outcome").text],
    ["Direction", exactValue(item, "direction").text, exactValue(item, "direction").kind],
    ["Structure", exactValue(item, "structure").text, exactValue(item, "structure").kind],
  ]));
  fragment.append(decision);
  const readiness = item.execution_assessment;
  if (readiness) {
    const section = element("section", "audit-section execution-readiness");
    section.append(element("h3", null, "Execution readiness — analytical only"));
    section.append(definitionList([
      ["Signal verdict (unchanged)", exactValue(item, "verdict").text],
      ["Intended structure", readiness.intended_structure_kind],
      ["Constructibility", readiness.status],
      ["Available structure", readiness.available_structure_kind || "Unknown"],
      ["Reason", readiness.reason_code || "None"],
    ]));
    for (const leg of readiness.exact_legs || []) {
      section.append(element("h4", null, `Exact leg — ${leg.role}`));
      section.append(definitionList([
        ["Contract identity", leg.canonical_contract_identity],
        ["Contract", `${leg.call_or_put} ${leg.expiration} ${leg.strike}`],
        ["Position / quantity", `${leg.long_or_short} / ${leg.quantity}`],
        ["Bid / ask / midpoint", `${leg.bid ?? "Unknown"} / ${leg.ask ?? "Unknown"} / ${leg.midpoint ?? "Unknown"}`],
        ["Target / actual delta", `${leg.target_delta ?? "Not declared"} / ${leg.actual_delta ?? "Unknown"}`],
      ]));
    }
    const entry = readiness.modeled_entry;
    if (entry) section.append(definitionList([
      ["Modeled entry", entry.modeled_net_debit_or_credit],
      ["Fill assumption", `${entry.reference}; ${entry.semantics}`],
    ]));
    const surface = item.modeled_pnl;
    if (surface) {
      section.append(element("h4", null, "Modeled P&L at front expiration"));
      section.append(definitionList([
        ["Spot reference", surface.spot_reference],
        ["Model", surface.valuation_model_and_version],
        ["Fill assumption", surface.entry_fill_assumption],
        ["Rate / dividend", `${surface.annual_risk_free_rate} / ${surface.annual_dividend_yield}`],
        ["Disclosure", surface.semantics],
      ]));
      const graph = element("div", "pnl-graph");
      const values = surface.points.map((point) => Number(point.modeled_pnl));
      const maximum = Math.max(1, ...values.map((value) => Math.abs(value)));
      for (const point of surface.points) {
        const row = element("div", "pnl-point");
        const value = Number(point.modeled_pnl);
        const bar = element("span", value >= 0 ? "pnl-bar pnl-bar--gain" : "pnl-bar pnl-bar--loss");
        bar.style.width = `${Math.max(1, Math.abs(value) / maximum * 100)}%`;
        row.append(element("code", null, point.underlying_price), bar, element("code", null, point.modeled_pnl));
        graph.append(row);
      }
      section.append(graph);
    }
    if (readiness.status === "constructible_as_intended") {
      const form = element("form", "pnl-assumptions");
      form.append(element("h4", null, "Model with explicit assumptions"));
      const fields = [
        ["valuation_time", "Front-expiration valuation time (ISO UTC)"],
        ["spot_reference", "Spot reference"],
        ["underlying_price_grid", "Price grid (comma separated)"],
        ["volatility_by_contract", "Back-leg IV by contract identity (JSON object)"],
        ["annual_risk_free_rate", "Annual risk-free rate"],
        ["annual_dividend_yield", "Annual dividend yield"],
        ["contract_multiplier", "Contract multiplier"],
      ];
      for (const [name, labelText] of fields) {
        const label = element("label", null, labelText);
        const input = element("input"); input.name = name; input.required = true;
        label.append(input); form.append(label);
      }
      const button = element("button", "button", "Calculate modeled P&L");
      button.type = "submit"; form.append(button);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const values = Object.fromEntries(new FormData(form));
        handlers.modelPnl(item, {
          valuation_time: values.valuation_time,
          spot_reference: values.spot_reference,
          underlying_price_grid: String(values.underlying_price_grid).split(",").map((value) => value.trim()),
          volatility_by_contract: JSON.parse(String(values.volatility_by_contract)),
          annual_risk_free_rate: values.annual_risk_free_rate,
          annual_dividend_yield: values.annual_dividend_yield,
          contract_multiplier: values.contract_multiplier,
        });
      });
      section.append(form);
    }
    fragment.append(section);
  }
  fragment.append(gateSection(item.gate_results));
  fragment.append(objectSection("Canonical facts", item.canonical_facts));
  fragment.append(objectSection("Named derived facts", item.named_derived_facts, item.formula_versions));
  fragment.append(objectSection("Formula versions", item.formula_versions));

  const reasons = element("section", "audit-section");
  reasons.append(element("h3", null, "Reasons and assumptions"));
  reasons.append(definitionList([
    ["Reason codes", exactValue(item, "reason_codes").text, exactValue(item, "reason_codes").kind],
    ["Assumptions", exactValue(item, "assumptions").text, exactValue(item, "assumptions").kind],
    ["Warnings", exactValue(item, "warnings").text, exactValue(item, "warnings").kind],
    ["Blockers", exactValue(item, "blockers").text, exactValue(item, "blockers").kind],
  ]));
  fragment.append(reasons);

  const temporal = element("section", "audit-section");
  temporal.append(element("h3", null, "Temporal metadata"));
  temporal.append(definitionList([
    ["Observed", exactValue(item, "observed_at").text],
    ["Received", exactValue(item, "received_at").text],
    ["Evaluated", exactValue(item, "evaluated_at").text],
    ["Persisted", exactValue(item, "persisted_at").text],
    ["Freshness", exactValue(item, "freshness_status").text],
    ["Usability", exactValue(item, "usability_status").text],
    ["Usability reason", exactValue(item, "usability_reason").text],
    ["Input skew seconds", exactValue(item, "input_time_skew_seconds").text],
  ]));
  fragment.append(temporal);
  fragment.append(objectSection("Provenance", Object.fromEntries((item.provenance || []).map((value, index) => [`evidence_${index + 1}`, value]))));

  const disclosure = element("details", "raw-json");
  disclosure.append(element("summary", null, "Raw JSON contract"));
  disclosure.append(element("pre", null, JSON.stringify(item, null, 2)));
  fragment.append(disclosure);
  return fragment;
}

function healthView(model) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "RUNTIME HEALTH AND PERSISTED SNAPSHOT"));
  heading.append(element("h2", null, "Service state"));
  heading.append(element("p", null, "Infrastructure checks and exact counts from the latest persisted rows—not a single run."));
  fragment.append(heading);
  const analyticalHeading = element("section", "page-heading");
  analyticalHeading.append(element("p", "eyebrow", "ANALYTICAL COMPLETENESS"));
  analyticalHeading.append(element("h2", null, "Strategy evaluation state"));
  analyticalHeading.append(element("p", null, "Latest persisted state by strategy. This is separate from service health and data freshness."));
  fragment.append(analyticalHeading);
  const analyticalGrid = element("div", "health-grid");
  for (const funnel of model.strategyHealth?.strategies || []) {
    const value = {
      subjects: funnel.active_subjects,
      evaluated: funnel.evaluated,
      missing_data: funnel.missing_data,
      no_signal: funnel.no_signal,
      watch: funnel.watch,
      pass: funnel.passed,
    };
    const card = element("article", "health-card");
    card.append(element("h3", null, funnel.strategy_id), element("code", null, JSON.stringify(value)));
    analyticalGrid.append(card);
  }
  if (!(model.strategyHealth?.strategies || []).length) {
    analyticalGrid.append(element("p", null, "Analytical state unavailable."));
  }
  fragment.append(analyticalGrid);
  const grid = element("div", "health-grid");
  const cards = [
    ["Health endpoint", JSON.stringify(model.health || "Unavailable")],
    ["Readiness endpoint", JSON.stringify(model.readiness || "Unavailable")],
    ["API contract", model.apiVersion || "Revision unavailable"],
    ["Application version", model.buildIdentity?.application_version || "Unavailable"],
    ["Release revision", model.buildIdentity?.release_sha || "Unavailable"],
    ["Persisted rows", String(model.results.length)],
    ["Earliest evaluated", model.evaluatedRange.earliest],
    ["Latest evaluated", model.evaluatedRange.latest],
    ["Verdicts", JSON.stringify(model.counts.verdict)],
    ["Evaluation states", JSON.stringify(model.counts.evaluation_state)],
    ["Freshness states", JSON.stringify(model.counts.freshness_status)],
    ["Usability states", JSON.stringify(model.counts.usability_status)],
  ];
  for (const [title, value] of cards) {
    const card = element("article", "health-card");
    card.append(element("h3", null, title), element("code", null, value));
    grid.append(card);
  }
  fragment.append(grid);
  return fragment;
}

export function renderApp(root, model, handlers) {
  root.replaceChildren();
  root.append(shellHeader(model, handlers));
  const main = element("main", "main-content"); main.id = "main";
  main.append(connectionPanel(handlers, model.hasToken));
  if (model.error) {
    const error = element("section", "error-banner");
    error.append(element("strong", null, "Unable to read the persisted API state."), element("span", null, model.error));
    main.append(error);
  }
  if (model.loading) main.append(element("div", "loading-bar", "Reading persisted state…"));
  if (model.route.name === "detail") {
    if (model.detail) main.append(detailView(model.detail, handlers));
    else main.append(element("p", "empty-state empty-state--large", "Result not found in the persisted snapshot."));
  } else if (model.route.name === "health") {
    main.append(healthView(model));
  } else {
    main.append(resultsView(model, handlers));
  }
  root.append(main);
  const footer = element("footer", "footer");
  footer.append(element("span", null, "READ-ONLY"), element("span", null, "No refresh, trade, or brokerage actions"));
  root.append(footer);
}

export { exactValue };
