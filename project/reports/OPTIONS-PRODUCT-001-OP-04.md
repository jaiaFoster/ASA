# OPTIONS-PRODUCT-001 — OP-04 payoff visualization

Baseline: `main@bf9ecb5`  
Operational issue: [#474](https://github.com/jaiaFoster/ASA/issues/474)

## Visualization boundary

The deterministic payoff owner now supplies a default display grid derived
only from exact canonical strikes. The API accepts that default when a caller
does not provide an explicit scenario grid. Financial values still come only
from the versioned server model; the UI does not price legs or reconstruct
payoff.

The Intelligence Console renders canonical payoff/model points as an
accessible SVG line chart with:

- a labeled zero-profit reference;
- explicit deterministic-terminal versus model-dependent-front-expiration
  headings and disclosures;
- the model and entry assumptions adjacent to the chart;
- a screen-reader label and an expandable exact-value text representation;
- explicit wording that modeled values are not guaranteed returns.

Same-expiration verticals load their deterministic payoff automatically.
Calendars continue to require explicit volatility/rate/dividend assumptions
before the existing front-expiration model is shown. No intrinsic-only
calendar substitution is possible.

## Proof

- deterministic grid is ordered, includes exact strikes, and is reproducible;
- API default-grid behavior is pinned;
- DOM behavior proves accessible graph labeling and exact textual values;
- no UI-owned valuation, provider acquisition, or broker mutation.

Validation: 3,467 repository tests passed / 48 skipped; 15 Intelligence
Console DOM tests and 7 frontend tests passed; generation, lint, typecheck, and
production builds are green.
