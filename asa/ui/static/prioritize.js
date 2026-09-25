// OI-06 transparent prioritization. Opportunity volume is sparse (a handful of
// qualifying rows per session), so this is ordering and filtering over
// currently trustworthy quantities only -- never a score, never a strategy
// ranking, and never weighted by forward outcomes. Every ordering key is
// displayed beside the row it orders.

// Forward-outcome evidence stays out of ordering until a strategy has at least
// this many observed outcomes with a modeled P&L. Even above the guard, this
// version only reports eligibility; empirical weighting is not implemented.
export const MINIMUM_OUTCOME_SAMPLE = 30;

export const PRIORITY_KEYS = [
  "Actionability: a complete proposal before a qualifying signal without one",
  "Evidence: usable and live/fresh before anything else",
  "Evidence age: newest observation first",
  "Tie-break: strategy then symbol (alphabetical, deterministic)",
];

const FRESH = new Set(["live", "fresh"]);

export function isQualifying(result) {
  return String(result.evaluation_state).toLowerCase() === "pass";
}

// entry: { result, stock, proposal } where proposal is the option trade
// proposal or stock proposal response, or null when none is available.
export function describeOpportunity(entry) {
  const { result, stock, proposal } = entry;
  const complete = stock
    ? proposal?.status === "actionable"
    : proposal?.status === "available";
  const evidenceTrusted =
    result.usability_status === "usable" && FRESH.has(String(result.freshness_status));
  let maximumLoss = "unknown";
  if (stock) maximumLoss = "not stated (stock)";
  else if (proposal?.maximum_loss) {
    maximumLoss = proposal.maximum_loss.value ?? proposal.maximum_loss.state;
  }
  return {
    key: `${result.signal_id}:${result.symbol}`,
    signalId: result.signal_id,
    symbol: result.symbol,
    assetClass: stock ? "stock" : "option",
    actionability: complete ? "complete proposal" : "qualifying signal, no complete proposal",
    actionabilityTier: complete ? 0 : 1,
    evidence: `${result.freshness_status} / ${result.usability_status}`,
    evidenceTier: evidenceTrusted ? 0 : 1,
    observedAt: String(result.observed_at),
    definedRisk: !stock && proposal?.maximum_loss?.value != null,
    maximumLoss,
    liquidity: stock ? "not applicable" : (proposal?.liquidity ?? "unknown"),
  };
}

export function compareOpportunities(left, right) {
  return (
    left.actionabilityTier - right.actionabilityTier ||
    left.evidenceTier - right.evidenceTier ||
    // ISO-8601 UTC strings order lexically; newer first.
    (left.observedAt < right.observedAt ? 1 : left.observedAt > right.observedAt ? -1 : 0) ||
    left.signalId.localeCompare(right.signalId) ||
    left.symbol.localeCompare(right.symbol)
  );
}

export function prioritizeOpportunities(entries, filters = {}) {
  return entries
    .map(describeOpportunity)
    .filter(
      (item) =>
        (!filters.assetClass || item.assetClass === filters.assetClass) &&
        (!filters.signal || item.signalId === filters.signal) &&
        (!filters.completeOnly || item.actionabilityTier === 0) &&
        (!filters.definedRiskOnly || item.definedRisk),
    )
    .sort(compareOpportunities);
}

// Per-strategy forward-outcome sample sizes and the guard verdict. `rows` is
// the Outcomes view's [{ candidate, outcomes }] corpus, or null when absent.
export function outcomeSampleGuard(rows) {
  if (!rows) return null;
  const byStrategy = new Map();
  for (const { candidate, outcomes } of rows) {
    const entry = byStrategy.get(candidate.strategy_id) || { tracked: 0, withPnl: 0 };
    entry.tracked += 1;
    entry.withPnl += outcomes.outcomes.filter((item) => item.modeled_pnl != null).length;
    byStrategy.set(candidate.strategy_id, entry);
  }
  return [...byStrategy.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([strategy, entry]) => ({
      strategy,
      ...entry,
      guard:
        entry.withPnl >= MINIMUM_OUTCOME_SAMPLE
          ? "sample meets guard; not used in ordering (weighting not implemented)"
          : `n=${entry.withPnl} < ${MINIMUM_OUTCOME_SAMPLE}; not used in ordering`,
    }));
}
