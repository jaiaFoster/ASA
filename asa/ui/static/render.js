import {
  MINIMUM_OUTCOME_SAMPLE,
  PRIORITY_KEYS,
  outcomeSampleGuard,
  prioritizeOpportunities,
} from "./prioritize.js";
import { isStockSignal } from "./state.js";

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
  const primaryLinks = [
    { href: "#/results", label: "Latest results", routeName: "results" },
    { href: "#/opportunities", label: "Opportunities", routeName: "opportunities" },
    { href: "#/stocks", label: "Stocks", routeName: "stocks" },
    { href: "#/strategies", label: "Strategy library", routeName: "strategies" },
    { href: "#/outcomes", label: "Outcomes", routeName: "outcomes" },
    { href: "#/health", label: "Runtime health", routeName: "health" },
  ];
  for (const { href, label, routeName } of primaryLinks) {
    const link = element("a", model.route.name === routeName ? "active" : "", label);
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
  heading.append(element("p", null, "Freshness and usability describe evidence; evaluation state describes whether analysis completed. Fresh missing-data rows remain analytically incomplete."));
  fragment.append(heading);

  const summary = element("section", "summary-grid");
  const summaries = [
    ["Visible rows", String(model.visible.length)],
    ["Loaded rows", String(model.results.length)],
    ["Active latest-state rows", String(model.resultsTotal)],
    ["Retained non-active rows", String(model.retainedNonactiveTotal)],
    ["Last fetched", model.fetchedAt || "Not fetched"],
    ["Revision", model.buildIdentity?.release_sha || "Unavailable"],
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

function tradeQuantityText(quantity) {
  if (quantity.value != null) return quantity.value;
  return quantity.reason ? `${quantity.state} (${quantity.reason})` : quantity.state;
}

const STOCK_STATUS_LABELS = {
  actionable: "Strategy action",
  no_action: "No action emitted",
  unknown: "Evaluation incomplete",
};

function stockProposalCard(proposal) {
  const card = element(
    "section",
    `trade-card stock-card${proposal.status === "actionable" ? "" : " trade-card--unavailable"}`,
  );
  card.append(element("p", "eyebrow", "STOCK OPPORTUNITY · ANALYTICAL, NOT AN ORDER"));
  card.append(element(
    "h3",
    null,
    `${proposal.instrument} · ${proposal.action ?? STOCK_STATUS_LABELS[proposal.status]}`,
  ));
  const rows = [
    ["Strategy", `${proposal.strategy_id}@${proposal.strategy_version}`],
    ["Status", proposal.status],
    ["Action", proposal.action ?? `none (${proposal.action_reason})`],
    ["Signal verdict", proposal.signal_verdict ?? "none"],
    ["Evidence observed", proposal.evidence_observed_at],
    ["Freshness", `${proposal.freshness} (${proposal.evidence_age_seconds}s old)`],
    ["Allocation", proposal.allocation ?? `none (${proposal.allocation_reason})`],
    ...proposal.signal_metrics.map((metric) => [metric.name, metric.value]),
  ];
  if (proposal.unknown_reasons.length) {
    rows.push(["Unknown because", proposal.unknown_reasons.join("; ")]);
  }
  card.append(definitionList(rows));
  const why = element("details", "trade-why");
  why.append(element("summary", null, "Why this action?"));
  const sections = [
    ["Rationale", proposal.rationale],
    ["Invalidation", proposal.invalidation_notes],
    ["Warnings", proposal.warnings],
    ["Provenance", proposal.provenance],
  ];
  for (const [title, values] of sections) {
    if (!values.length) continue;
    why.append(element("h4", null, title));
    const list = element("ul");
    list.append(...values.map((value) => element("li", null, value)));
    why.append(list);
  }
  card.append(why);
  card.append(element(
    "p",
    "track-disclosure",
    "ASA does not size positions or estimate returns unless the strategy defines them.",
  ));
  return card;
}

function detailView(item, handlers, capabilities) {
  const fragment = document.createDocumentFragment();
  const back = element("a", "back-link", "← Latest results"); back.href = "#/results"; fragment.append(back);
  const heading = element("section", "page-heading detail-heading");
  const asset = isStockSignal(capabilities, item.signal_id) ? "STOCK / ETF" : "OPTIONS";
  heading.append(element("p", "eyebrow", `RESULT AUDIT · ${asset}`));
  heading.append(element("h2", null, `${item.signal_id} / ${item.symbol}`));
  const states = element("div", "badge-row badge-row--large");
  states.append(badge(item.verdict, "verdict"), badge(item.evaluation_state, "evaluation"), badge(item.outcome, "state"));
  heading.append(states);
  fragment.append(heading);

  if (item.stock_proposal) fragment.append(stockProposalCard(item.stock_proposal));

  const proposal = item.trade_proposal;
  if (proposal?.status === "available") {
    const trade = element("section", "trade-card");
    trade.append(element("p", "eyebrow", "PROPOSED TRADE · ANALYTICAL, NOT AN ORDER"));
    trade.append(element("h3", null, `${proposal.underlying} ${proposal.structure}`));
    trade.append(definitionList([
      ["Strategy", `${proposal.strategy_id}@${proposal.strategy_version}`],
      ["Modeled entry", `${proposal.modeled_net_debit_or_credit} (${proposal.entry_model_version})`],
      ["Constructibility", proposal.constructibility],
      ["Liquidity", proposal.liquidity],
      ["Capital required", tradeQuantityText(proposal.capital_required)],
      ["Maximum loss", tradeQuantityText(proposal.maximum_loss)],
      ["Maximum profit", tradeQuantityText(proposal.maximum_profit)],
      ["Breakeven", tradeQuantityText(proposal.breakeven)],
    ]));
    const legs = element("div", "trade-legs");
    for (const leg of proposal.legs) {
      const card = element("article", "trade-leg");
      card.append(
        element("strong", null, `${leg.buy_or_sell.toUpperCase()} ${leg.quantity} ${leg.call_or_put.toUpperCase()}`),
        element("span", null, `${leg.expiration} · strike ${leg.strike}`),
        element("small", null, `bid / ask / mid ${leg.bid ?? "Unknown"} / ${leg.ask ?? "Unknown"} / ${leg.midpoint ?? "Unknown"}`),
      );
      legs.append(card);
    }
    trade.append(legs);
    if (item.tracked_candidate) {
      trade.append(element("p", "track-confirmation", `Tracked · ${item.tracked_candidate.id}`));
    } else {
      const track = element("button", "button button--primary", "Track This");
      track.type = "button";
      track.addEventListener("click", () => handlers.trackProposal(item));
      trade.append(track);
    }
    trade.append(element(
      "p",
      "track-disclosure",
      "Tracking preserves this proposal. It does not place an order or imply a fill.",
    ));
    if (item.terminal_payoff) {
      trade.append(element("h4", null, "Deterministic expiration payoff"));
      trade.append(definitionList([
        ["Expiration", item.terminal_payoff.expiration],
        ["Model", item.terminal_payoff.model_version],
        ["Entry assumption", item.terminal_payoff.entry_fill_assumption],
        ["Disclosure", item.terminal_payoff.semantics],
      ]));
      trade.append(payoffVisualization(
        item.terminal_payoff.points,
        "payoff",
        "Deterministic expiration payoff by underlying price",
      ));
    }
    const why = element("details", "trade-why");
    why.append(element("summary", null, "Why this trade?"));
    why.append(element("h4", null, "Rationale"));
    const rationale = element("ul");
    rationale.append(...proposal.rationale.map((value) => element("li", null, value)));
    why.append(rationale);
    why.append(element("h4", null, "Risks and invalidation"));
    const risks = element("ul");
    risks.append(...[...proposal.risk_notes, ...proposal.invalidation_notes].map((value) => element("li", null, value)));
    why.append(risks);
    why.append(element("h4", null, "Model assumptions"));
    const modelAssumptions = element("ul");
    modelAssumptions.append(...proposal.assumptions.map((value) => element("li", null, value)));
    why.append(modelAssumptions);
    why.append(element("p", "trade-evidence", `Evidence snapshot ${proposal.evidence_snapshot_identity}`));
    trade.append(why);
    fragment.append(trade);
  } else if (proposal?.status === "unavailable") {
    const unavailable = element("section", "trade-card trade-card--unavailable");
    unavailable.append(element("p", "eyebrow", "SIGNAL ≠ EXECUTABLE TRADE"));
    unavailable.append(element("h3", null, "No truthful trade proposal is available"));
    unavailable.append(definitionList([
      ["Signal verdict (unchanged)", exactValue(item, "verdict").text],
      ["Execution readiness", proposal.constructibility],
      ["Blocker category", proposal.blocker_category],
      ["Exact blocker", proposal.reason_code],
    ]));
    unavailable.append(element("p", "trade-blocker-message", proposal.user_message));
    fragment.append(unavailable);
  }

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
      section.append(payoffVisualization(
        surface.points,
        "modeled_pnl",
        "Modeled front-expiration profit and loss by underlying price",
      ));
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

function payoffVisualization(points, valueKey, label) {
  const wrapper = element("figure", "payoff-chart");
  const parsed = points.map((point) => ({
    price: Number(point.underlying_price), value: Number(point[valueKey]), raw: point,
  }));
  if (!parsed.length || parsed.some((point) => !Number.isFinite(point.price) || !Number.isFinite(point.value))) {
    wrapper.append(element("p", "empty-state", "Payoff visualization unavailable."));
    return wrapper;
  }
  const width = 720; const height = 260; const padding = 32;
  const prices = parsed.map((point) => point.price);
  const values = parsed.map((point) => point.value);
  const minX = Math.min(...prices); const maxX = Math.max(...prices);
  const minY = Math.min(0, ...values); const maxY = Math.max(0, ...values);
  const xRange = Math.max(1, maxX - minX); const yRange = Math.max(1, maxY - minY);
  const x = (value) => padding + (value - minX) / xRange * (width - 2 * padding);
  const y = (value) => height - padding - (value - minY) / yRange * (height - 2 * padding);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label);
  const zero = document.createElementNS("http://www.w3.org/2000/svg", "line");
  zero.setAttribute("x1", String(padding)); zero.setAttribute("x2", String(width - padding));
  zero.setAttribute("y1", String(y(0))); zero.setAttribute("y2", String(y(0)));
  zero.setAttribute("class", "payoff-zero-line");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", parsed.map((point) => `${x(point.price)},${y(point.value)}`).join(" "));
  line.setAttribute("class", "payoff-line");
  svg.append(zero, line); wrapper.append(svg);
  wrapper.append(element("figcaption", null, `${label}. Values use the displayed model and entry assumptions; they are not guaranteed returns.`));
  const valuesDisclosure = element("details", "payoff-values");
  valuesDisclosure.append(element("summary", null, "Show exact plotted values"));
  valuesDisclosure.append(definitionList(parsed.map((point) => [
    String(point.raw.underlying_price), String(point.raw[valueKey]),
  ])));
  wrapper.append(valuesDisclosure);
  return wrapper;
}


function factInspector(value) {
  const disclosure = element("details", "fact-inspector");
  disclosure.append(element("summary", null, "Inspect fact lineage"));
  if (!value?.lineage) {
    disclosure.append(element("p", null, `Lineage unavailable: ${value?.unknown_reason || "not_recorded"}`));
    return disclosure;
  }
  const lineage = value.lineage;
  disclosure.append(definitionList([
    ["Fact", lineage.semantic_name],
    ["Fact identity", lineage.fact_id],
    ["Source", lineage.source],
    ["Observed", lineage.observed_at],
    ["Fetched", lineage.fetched_at],
    ["Computed", lineage.computed_at],
    ["Snapshot", lineage.snapshot_id],
    ["Freshness", lineage.freshness_status],
    ["Usability", lineage.usability_status],
    ["Formula", lineage.formula_id],
    ["Formula version", lineage.formula_version],
  ]));
  if (lineage.inputs?.length) {
    disclosure.append(element("pre", null, JSON.stringify(lineage.inputs, null, 2)));
  }
  return disclosure;
}

function stockPositionView(model) {
  const fragment = document.createDocumentFragment();
  const positions = model.positions;
  if (!positions) {
    fragment.append(element("p", "empty-state", "Position details unavailable."));
    return fragment;
  }
  const valuations = new Map(
    positions.data.equity_valuations.map((item) => [item.position_key, item]),
  );
  const grid = element("div", "health-grid");
  for (const position of positions.data.equity_positions) {
    const key = `${position.account_id}:equity:${position.symbol}`;
    const valuation = valuations.get(key);
    const card = element("article", "health-card");
    card.append(element("h3", null, position.symbol));
    card.append(definitionList([
      ["Quantity", String(position.quantity)],
      ["Average cost", String(position.average_cost)],
      ["Observed", position.observed_at],
      ["Position source", position.original_provider],
      ["Market value", valuation?.market_value?.amount ?? "UNKNOWN"],
      ["Unrealized P&L", valuation?.profit_and_loss?.amount ?? "UNKNOWN"],
      ["Unrealized P&L %", valuation?.profit_and_loss_percent?.amount ?? "UNKNOWN"],
    ]));
    if (valuation) {
      card.append(factInspector(valuation.market_value));
      card.append(factInspector(valuation.profit_and_loss));
      card.append(factInspector(valuation.profit_and_loss_percent));
    }
    grid.append(card);
  }
  if (!positions.data.equity_positions.length) {
    grid.append(element("p", "empty-state", "No equity holdings in this snapshot."));
  }
  fragment.append(element("h3", null, "Equity holdings"), grid);
  return fragment;
}

function stockPortfolioView(model) {
  const fragment = document.createDocumentFragment();
  const portfolio = model.portfolio;
  if (!portfolio) {
    fragment.append(
      element("p", "empty-state empty-state--large", "No published portfolio is available."),
    );
    return fragment;
  }

  const summary = element("section", "summary-grid");
  const summaries = [
    ["Accounts", String(portfolio.data.account_count)],
    ["Equity positions", String(portfolio.data.equity_position_count)],
    ["Option legs", String(portfolio.data.option_leg_count)],
    ["Provider", portfolio.data.provider],
    ["Freshness", portfolio.freshness.status],
    ["Serving last success", String(portfolio.freshness.serving_last_success)],
  ];
  for (const [label, value] of summaries) {
    const card = element("article", "summary-card");
    card.append(element("span", null, label), element("strong", null, value));
    summary.append(card);
  }
  fragment.append(summary);

  const grid = element("div", "health-grid");
  for (const account of portfolio.data.accounts) {
    const card = element("article", "health-card");
    card.append(element("h3", null, `${account.display_name} (${account.account_type})`));
    const badges = element("div", "badge-row");
    badges.append(badge(account.holdings_status, "holdings"));
    card.append(badges);
    card.append(
      definitionList([
        ["Identifier", account.external_account_id],
        ["Provider", account.provider],
        ["Currency", account.currency],
        [
          "Cash balance",
          exactValue(account, "cash_balance").text,
          exactValue(account, "cash_balance").kind,
        ],
        [
          "Buying power",
          exactValue(account, "buying_power").text,
          exactValue(account, "buying_power").kind,
        ],
        [
          "Account value",
          exactValue(account, "account_value").text,
          exactValue(account, "account_value").kind,
        ],
        ["Holdings as of", account.holdings_as_of],
        ["Observed", account.observed_at],
      ]),
    );
    grid.append(card);
  }
  if (!portfolio.data.accounts.length) {
    grid.append(element("p", "empty-state", "No accounts in the published snapshot."));
  }
  fragment.append(grid);
  fragment.append(stockPositionView(model));
  return fragment;
}

function stockStrategiesView(model) {
  const fragment = document.createDocumentFragment();
  const items = model.results.filter((item) => isStockSignal(model.capabilities, item.signal_id));

  const tableWrap = element("div", "table-wrap");
  const table = element("table", "results-table");
  const head = element("thead");
  const headRow = element("tr");
  for (const title of [
    "Benchmark",
    "Symbol",
    "Verdict",
    "Direction",
    "Price",
    "SMA 10M",
    "Evaluated",
    "Freshness",
    "Usability",
  ]) {
    headRow.append(element("th", null, title));
  }
  head.append(headRow);
  table.append(head);
  const body = element("tbody");
  for (const item of items) {
    const row = element("tr");
    const identity = element("td");
    identity.append(resultLink(item), element("small", null, `v${item.signal_version}`));
    row.append(identity);
    row.append(element("td", null, item.symbol));
    const verdict = element("td");
    verdict.append(badge(item.verdict, "verdict"));
    row.append(verdict);
    row.append(element("td", null, exactValue(item, "direction").text));
    row.append(element("td", null, exactValue(item.metrics, "price").text));
    row.append(element("td", null, exactValue(item.metrics, "sma_10m_completed_months").text));
    row.append(element("td", "timestamp", String(item.evaluated_at)));
    const freshness = element("td");
    freshness.append(badge(item.freshness_status, "freshness"));
    row.append(freshness);
    const usability = element("td");
    usability.append(badge(item.usability_status, "usability"));
    row.append(usability);
    body.append(row);
  }
  table.append(body);
  tableWrap.append(table);
  fragment.append(tableWrap);
  if (!items.length) {
    fragment.append(
      element("p", "empty-state empty-state--large", "No persisted stock-benchmark results yet."),
    );
  }
  return fragment;
}

function stocksView(model) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "STOCK BENCHMARKS AND HOLDINGS"));
  heading.append(element("h2", null, "Stocks"));
  heading.append(element("p", null, "Portfolio holdings and SPY benchmark results, read-only."));
  fragment.append(heading);

  const subnav = element("nav", "secondary-nav");
  subnav.setAttribute("aria-label", "Stocks sections");
  const subLinks = [
    { href: "#/stocks/portfolio", label: "Portfolio", subview: "portfolio" },
    { href: "#/stocks/strategies", label: "Stock strategies", subview: "strategies" },
  ];
  for (const { href, label, subview } of subLinks) {
    const link = element("a", model.route.subview === subview ? "active" : "", label);
    link.href = href;
    subnav.append(link);
  }
  fragment.append(subnav);

  fragment.append(
    model.route.subview === "strategies" ? stockStrategiesView(model) : stockPortfolioView(model),
  );
  return fragment;
}

const OUTCOME_HORIZONS = ["d1", "d5", "d10", "first_expiration"];

function outcomeCell(outcome) {
  if (!outcome) return "not scheduled";
  if (outcome.status !== "observed") return outcome.status;
  if (outcome.modeled_pnl != null) return `P&L ${outcome.modeled_pnl}`;
  return `observed · P&L unknown (${outcome.unknown_reasons.join(", ") || "n/a"})`;
}

function outcomesView(model) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "FORWARD OUTCOMES · PAPER / MODELED, NOT BROKERAGE FILLS"));
  heading.append(element("h2", null, "What ASA's proposals did next"));
  heading.append(element(
    "p",
    null,
    "Modeled midpoint marks against each proposal's frozen modeled entry, sampled at "
      + "fixed horizons (not path extremes). The two corpora below are reported separately "
      + "and never pooled; no strategy is ranked from them.",
  ));
  fragment.append(heading);
  fragment.append(outcomeCorpusSection(
    "System-actionable corpus",
    "Every option proposal ASA itself judged actionable: the first per strategy, symbol and "
      + "session, at most 8 per session. Not chosen by anyone, but limited to ASA's own gates.",
    model.systemEnrollments,
    model.systemEnrollmentsError,
    "Enrolled",
    "enrolled",
  ));
  fragment.append(outcomeCorpusSection(
    "User-tracked corpus",
    "Only proposals someone chose to track, so it is selection-biased and small.",
    model.forwardOutcomes,
    model.forwardOutcomesError,
    "Tracked",
    "tracked",
  ));
  return fragment;
}

function outcomeCorpusSection(title, disclosure, rows, error, timeLabel, noun) {
  const section = element("section", "outcome-corpus");
  section.append(element("h3", null, title), element("p", null, disclosure));
  if (error) {
    section.append(element("p", "empty-state", `Outcomes unavailable: ${error}`));
    return section;
  }
  const loaded = rows || [];
  const byStrategy = new Map();
  for (const { candidate, outcomes } of loaded) {
    const entry = byStrategy.get(candidate.strategy_id) || { tracked: 0, observed: 0, withPnl: 0 };
    entry.tracked += 1;
    for (const item of outcomes.outcomes) {
      if (item.status === "observed") entry.observed += 1;
      if (item.modeled_pnl != null) entry.withPnl += 1;
    }
    byStrategy.set(candidate.strategy_id, entry);
  }
  const summary = element("div", "summary-grid");
  for (const [strategy, entry] of byStrategy) {
    const card = element("article", "summary-card");
    card.append(
      element("span", null, strategy),
      element(
        "strong",
        null,
        `${entry.tracked} ${noun} · ${entry.observed} observed · n=${entry.withPnl} with modeled P&L`,
      ),
    );
    summary.append(card);
  }
  section.append(summary);
  const tableWrap = element("div", "table-wrap");
  const table = element("table", "results-table outcomes-table");
  const head = element("thead");
  const headRow = element("tr");
  for (const heading of ["Strategy", "Symbol", timeLabel, ...OUTCOME_HORIZONS]) {
    headRow.append(element("th", null, heading));
  }
  head.append(headRow);
  table.append(head);
  const body = element("tbody");
  for (const { candidate, outcomes } of loaded) {
    const byHorizon = new Map(outcomes.outcomes.map((item) => [item.horizon_id, item]));
    const row = element("tr");
    row.append(
      element("td", null, `${candidate.strategy_id}@${candidate.strategy_version}`),
      element("td", null, candidate.symbol),
      element("td", "timestamp", candidate.tracked_at),
      ...OUTCOME_HORIZONS.map((horizon) => element("td", null, outcomeCell(byHorizon.get(horizon)))),
    );
    body.append(row);
  }
  table.append(body);
  tableWrap.append(table);
  section.append(tableWrap);
  if (!loaded.length) {
    section.append(element("p", "empty-state empty-state--large", `No ${noun} proposals yet.`));
  }
  return section;
}

function opportunitiesView(model, handlers) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "TRANSPARENT ORDERING · NOT A SCORE, NOT A STRATEGY RANKING"));
  heading.append(element("h2", null, "Qualifying opportunities"));
  heading.append(element(
    "p",
    null,
    "Only rows whose strategy qualified are listed. They are ordered by the keys below, "
      + "in order; every key is shown on its row. Forward outcomes do not affect ordering.",
  ));
  const keys = element("ol", "priority-keys");
  keys.append(...PRIORITY_KEYS.map((text) => element("li", null, text)));
  heading.append(keys);
  fragment.append(heading);

  const filters = element("form", "filter-bar");
  filters.setAttribute("aria-label", "Opportunity filters");
  const signals = [...new Set(model.opportunityEntries.map((item) => item.result.signal_id))].sort();
  for (const [key, labelText, values] of [
    ["assetClass", "Asset class", ["option", "stock"]],
    ["signal", "Strategy", signals],
  ]) {
    const label = element("label", null, labelText);
    const select = element("select");
    select.name = key;
    select.append(option("All", ""));
    for (const value of values) select.append(option(value, value));
    select.value = model.opportunityFilters[key];
    select.addEventListener("change", () => handlers.filterOpportunities(key, select.value));
    label.append(select);
    filters.append(label);
  }
  for (const [key, labelText] of [
    ["completeOnly", "Complete proposals only"],
    ["definedRiskOnly", "Stated maximum loss only"],
  ]) {
    const label = element("label", "checkbox-label", labelText);
    const input = element("input");
    input.type = "checkbox";
    input.name = key;
    input.checked = Boolean(model.opportunityFilters[key]);
    input.addEventListener("change", () => handlers.filterOpportunities(key, input.checked));
    label.prepend(input);
    filters.append(label);
  }
  fragment.append(filters);

  const ordered = prioritizeOpportunities(model.opportunityEntries, model.opportunityFilters);
  const tableWrap = element("div", "table-wrap");
  const table = element("table", "results-table opportunities-table");
  const head = element("thead");
  const headRow = element("tr");
  for (const title of ["#", "Identity", "Actionability", "Evidence", "Observed", "Maximum loss", "Liquidity"]) {
    headRow.append(element("th", null, title));
  }
  head.append(headRow);
  table.append(head);
  const body = element("tbody");
  ordered.forEach((item, index) => {
    const row = element("tr");
    const identity = element("td");
    const link = element("a", "result-link", `${item.signalId} / ${item.symbol}`);
    link.href = `#/results/${encodeURIComponent(item.signalId)}/${encodeURIComponent(item.symbol)}`;
    identity.append(link, element("small", null, item.assetClass));
    row.append(
      element("td", null, String(index + 1)),
      identity,
      element("td", null, item.actionability),
      element("td", null, item.evidence),
      element("td", "timestamp", item.observedAt),
      element("td", null, item.maximumLoss),
      element("td", null, item.liquidity),
    );
    body.append(row);
  });
  table.append(body);
  tableWrap.append(table);
  fragment.append(tableWrap);
  if (!ordered.length) {
    fragment.append(element("p", "empty-state empty-state--large", "No qualifying opportunities match these filters."));
  }

  const samples = element("section", "outcome-sample-guard");
  samples.append(element("h3", null, "Forward-outcome sample sizes"));
  samples.append(element(
    "p",
    null,
    `Outcome evidence could inform ordering only after a strategy has at least `
      + `${MINIMUM_OUTCOME_SAMPLE} observed outcomes with modeled P&L. Paper/modeled, not brokerage fills.`,
  ));
  for (const [label, rows, error] of [
    ["System-actionable", model.systemEnrollments, model.systemEnrollmentsError],
    ["User-tracked", model.forwardOutcomes, model.forwardOutcomesError],
  ]) {
    samples.append(element("h4", null, label));
    const guard = outcomeSampleGuard(rows);
    if (error) {
      samples.append(element("p", "empty-state", `Outcome samples unavailable: ${error}`));
    } else if (!guard) {
      samples.append(element("p", "empty-state", "Outcome samples not loaded."));
    } else if (!guard.length) {
      samples.append(element("p", "empty-state", "No proposals yet (n=0 for every strategy)."));
    } else {
      samples.append(definitionList(guard.map((item) => [
        item.strategy,
        `${item.tracked} proposals · n=${item.withPnl} with modeled P&L · ${item.guard}`,
      ])));
    }
  }
  fragment.append(samples);
  return fragment;
}

function strategyLibraryView(model) {
  const fragment = document.createDocumentFragment();
  const heading = element("section", "page-heading");
  heading.append(element("p", "eyebrow", "STRATEGY LIBRARY"));
  heading.append(element("h2", null, "Registered strategies"));
  heading.append(element(
    "p",
    null,
    "Declared contracts and current evaluation coverage from the latest persisted state. "
      + "Counts describe coverage, not strategy quality; no ranking is implied.",
  ));
  fragment.append(heading);
  const funnels = new Map(
    (model.strategyHealth?.strategies || []).map((item) => [item.strategy_id, item]),
  );
  const signals = model.capabilities?.signals || [];
  const tableWrap = element("div", "table-wrap");
  const table = element("table", "results-table strategy-library");
  const head = element("thead");
  const headRow = element("tr");
  for (const title of [
    "Strategy", "Version", "Asset", "Structure", "Category", "Required capabilities",
    "Active subjects", "Evaluated", "Missing data", "PASS", "WATCH",
    "Structure eligible", "Top typed unknown",
  ]) {
    headRow.append(element("th", null, title));
  }
  head.append(headRow);
  table.append(head);
  const body = element("tbody");
  for (const signal of signals) {
    const funnel = funnels.get(signal.signal_id);
    const stock = isStockSignal(model.capabilities, signal.signal_id);
    const topUnknown = [...(funnel?.typed_unknown_counts || [])]
      .sort((left, right) => right.count - left.count)[0];
    const row = element("tr");
    for (const value of [
      signal.signal_id,
      signal.signal_version,
      stock ? "Stock / ETF" : "Options",
      signal.structure,
      signal.category,
      signal.required_capabilities.join(", "),
      funnel ? String(funnel.active_subjects) : "UNKNOWN",
      funnel ? String(funnel.evaluated) : "UNKNOWN",
      funnel ? String(funnel.missing_data) : "UNKNOWN",
      funnel ? String(funnel.passed) : "UNKNOWN",
      funnel ? String(funnel.watch) : "UNKNOWN",
      stock ? "not applicable" : funnel ? String(funnel.structure_eligible_or_constructible) : "UNKNOWN",
      topUnknown ? `${topUnknown.reason} (${topUnknown.count})` : "none",
    ]) {
      row.append(element("td", null, value));
    }
    body.append(row);
  }
  table.append(body);
  tableWrap.append(table);
  fragment.append(tableWrap);
  if (!signals.length) {
    fragment.append(element("p", "empty-state empty-state--large", "Strategy catalog unavailable."));
  }
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
      missing_data_reasons: Object.fromEntries(
        (funnel.typed_unknown_counts || []).map((item) => [item.reason, item.count]),
      ),
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
    ["Loaded rows", String(model.results.length)],
    ["Active latest-state rows", String(model.resultsTotal)],
    ["Retained non-active rows", String(model.retainedNonactiveTotal)],
    ["Latest-state identity", model.resultsSnapshotIdentity || "Unavailable"],
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
    if (model.detail) main.append(detailView(model.detail, handlers, model.capabilities));
    else main.append(element("p", "empty-state empty-state--large", "Result not found in the persisted snapshot."));
  } else if (model.route.name === "health") {
    main.append(healthView(model));
  } else if (model.route.name === "opportunities") {
    main.append(opportunitiesView(model, handlers));
  } else if (model.route.name === "outcomes") {
    main.append(outcomesView(model));
  } else if (model.route.name === "strategies") {
    main.append(strategyLibraryView(model));
  } else if (model.route.name === "stocks") {
    main.append(stocksView(model));
  } else {
    main.append(resultsView(model, handlers));
  }
  root.append(main);
  const footer = element("footer", "footer");
  footer.append(element("span", null, "READ-ONLY"), element("span", null, "No refresh, trade, or brokerage actions"));
  root.append(footer);
}

export { exactValue };
