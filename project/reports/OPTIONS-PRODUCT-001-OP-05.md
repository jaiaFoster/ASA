# OPTIONS-PRODUCT-001 — OP-05 truthful failure experience

Baseline: `main@d2d782d`  
Operational issue: [#476](https://github.com/jaiaFoster/ASA/issues/476)

## Failure contract

Nonconstructible execution readiness now projects both the unchanged exact
reason code and a deterministic presentation category/message. The bounded
taxonomy covers stale evidence, earnings uncertainty, liquidity/spread,
missing volatility, missing delta/Greek, expiration, strike/contract
selection, quote/midpoint, unsupported structure, different structure, and no
strategy-selected structure. Unrecognized reasons remain visibly `unknown`
while preserving the exact code.

This taxonomy is presentation metadata only. It never changes the signal,
constructibility, acquisition behavior, or strategy policy.

## Product behavior

The Intelligence Console renders a dedicated non-executable card when a
signal lacks a truthful exact proposal. It shows, separately:

- the signal verdict, explicitly unchanged;
- execution-readiness status;
- blocker category;
- exact typed blocker code;
- a concise explanation.

A PASS can therefore remain PASS without being misrepresented as an
executable trade. ASA never substitutes a different structure or hides the
underlying reason.

## Proof

- parameterized blocker-category tests cover the required failure families;
- DOM behavior pins PASS versus nonconstructible separation and exact reason;
- generated API types retain category, message, and raw reason;
- no provider acquisition, strategy-semantic change, or broker mutation.

Validation: 3,476 repository tests passed / 48 skipped; 16 Intelligence
Console DOM tests and 7 frontend tests passed; generation, lint, typecheck, and
production builds are green.
