# Session-aware quote freshness

Quote age and quote usability are separate.

- Within the caller's maximum age, a quote is `fresh`.
- Outside that age while the exchange is closed, a quote from the latest
  completed US equity session is `prior_session`.
- A quote older than the latest completed session is `stale`.
- Missing or malformed provider timestamps fail schema validation.

`prior_session` observations remain canonical provider evidence and may satisfy
non-intraday acquisition with an explicit quality label. No provider, symbol,
or strategy name participates in this policy. Session semantics use
`America/New_York`, including weekends, modern exchange holidays, DST, and
early closes.

Strategy contracts carry a `FreshnessRequirement`. The default accepts
prior-session data. An intraday strategy can require an open session, reject
prior-session evidence, or declare a tighter maximum age. Shared runtime policy
evaluates these fields; it never branches on a strategy name.

Rollback: revert the TEMP-001/TEMP-002 commits. Existing latest results remain
intact; there is no schema migration or destructive data action.
