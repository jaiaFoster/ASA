# SPRINT-008D — PROD-004: Provider Quality Validation

Status: Complete at the code level. One item (Finnhub's live classification) requires a
Founder-run live check this agent could not execute — see Section 3.

Sprint reference: `docs/sprints/SPRINT-008D.yaml`
Repository commit at investigation time: `58c8d64` (`main`)

## 1. Objective

Investigate and resolve or precisely document the Finnhub authorization issue; validate that
provider capability routing correctly selects a provider for each canonical capability each
registered signal declares; verify Forward Factor's actual data requirements are met by at
least one enabled, working provider; document provider fallback behavior.

## 2. Provider capability inventory (confirmed against each provider's own declared capabilities)

| Provider | Declared capabilities (`market_data/<provider>.py`) |
|---|---|
| Tradier | `real_time_quote_v1`, `historical_bars_v1`, `option_chain_v1` |
| Finnhub | `real_time_quote_v1`, `historical_bars_v1`, `earnings_calendar_v1` |
| Alpha Vantage | `historical_bars_v1`, `earnings_calendar_v1` |

**Only Tradier declares `option_chain_v1`.** Every registered signal (Section 4) needs it.

## 3. The Finnhub authorization issue

`market_data/finnhub.py::_http_error` already classifies failures precisely, by HTTP status and
response body content (not guessed — read directly from the provider adapter's own code):

| Condition | Classification |
|---|---|
| HTTP 401 | `AUTHENTICATION_FAILED` — credential rejected outright |
| HTTP 403, body contains "premium"/"entitlement"/"subscription" | `ENTITLEMENT_MISSING` — credential is valid but the account's plan doesn't include this endpoint |
| HTTP 403, otherwise | `AUTHORIZATION_FAILED` |
| HTTP 429 | `RATE_LIMITED` |

**Most likely cause, based on this classification and Finnhub's own publicly documented API
tiers**: Finnhub's earnings calendar endpoint (the only capability this deployment uses Finnhub
for — see Section 2, Finnhub declares no `option_chain_v1`) requires a paid plan; a free-tier API
key produces exactly the 403 + "premium"-style body this code already classifies as
`ENTITLEMENT_MISSING`, not `AUTHENTICATION_FAILED`. This is a hypothesis, stated as one, not a
confirmed finding — it was not possible to verify against the live credential (Section 3.1).

### 3.1 What could and could not be verified directly

This investigation attempted to run the deployment's own existing, purpose-built diagnostic
(`POST /ops/market-data/validate {"providers": ["finnhub"]}` —
`docs/deployment/market-data-provider-diagnostics.md`) against production, via Railway's own
service-management tooling. That tooling can *generate and set* a sealed variable without ever
exposing its value (used successfully in ACT-001), but confirmed directly when asked here that it
**cannot read back an existing sealed variable's value** to construct an outbound authenticated
request — by the same design that keeps secrets from this agent. This is the correct security
behavior, not a defect, but it means this specific check requires the Founder.

**Requesting Founder action** — one safe, already-bounded, already-deployed command (no new code,
no new risk beyond what this endpoint is already designed for):

```bash
curl -sS -X POST https://asa-production-b2c4.up.railway.app/ops/market-data/validate \
  -H "Authorization: Bearer $ASA_OPERATIONS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"providers": ["finnhub"]}'
```

The response is secret-free by the endpoint's own design (`asa/market_data_ops/routes.py`'s
`CapabilityCheckResponse` model has no field capable of carrying a raw credential or payload).
Please paste the response back, or at minimum the `entitlement_status` and
`normalized_check_status` fields for the `earnings_calendar_v1` check, so this finding can be
confirmed or corrected.

## 4. Data-requirement verification (every registered signal, not just Forward Factor)

Read directly from each live adapter (`screening/live_adapters.py`), not inferred from the
registry's own declared metadata — and this surfaced a real discrepancy between the two:

| Signal | Capabilities actually used by the live adapter | Capabilities declared in `screening/registry.py` (public `/api/v1/capabilities`) |
|---|---|---|
| `forward_factor` | `real_time_quote_v1` (spot price) + `option_chain_v1` (expirations, combined chain across front/back) | `option_chain_v1` only |
| `skew_momentum` | `real_time_quote_v1` (spot price) + `option_chain_v1` (expirations, nearest-expiration chain) | `option_chain_v1` only |
| `earnings_calendar` | `earnings_calendar_v1` + `real_time_quote_v1` (spot price) + `option_chain_v1` (expirations, combined chain) | `earnings_calendar_v1`, `option_chain_v1` |

**Every one of the three registered signals actually requires `real_time_quote_v1` for live
acquisition, and none of the three declares it in `ScreeningStrategyDefinition.required_capabilities`.**
Confirmed by reading `_acquire_or_raise(fulfillment, symbol, MarketCapability.REAL_TIME_QUOTE_V1, ...)`
directly in each of `build_live_forward_factor_adapter`, `build_live_skew_momentum_adapter`, and
`build_live_earnings_calendar_adapter`. `acquire_expirations()` (used by all three) additionally
confirms `option_chain_v1` is required for expiration discovery, not only for the chain fetch
itself — already correctly declared.

**Impact**: none on this deployment's actual ability to run these signals — Tradier alone
supplies both `real_time_quote_v1` and `option_chain_v1` (Section 2), so PROD-001's universe
(forward_factor and skew_momentum, both Tradier-only) is unaffected in practice. The impact is on
the *public capabilities catalog's own accuracy*: `GET /api/v1/capabilities`
(`docs/api/agent-api-examples.md`) currently underclaims what a live refresh needs. An external
agent deciding whether it has "enough" provider coverage before calling `POST .../refresh`, based
solely on the declared `required_capabilities`, would not know a quote-capable provider is also
required.

**Recommendation, not implemented here**: add `real_time_quote_v1` to all three
`ScreeningStrategyDefinition.required_capabilities` tuples in `screening/adapters.py`'s
`TARGET_STRATEGY_DEFINITIONS`. Deliberately left out of this ticket's own scope — it touches the
registered strategy definitions and their exposed public metadata shape, which is more than a
"validate the existing thing" change, and deserves its own reviewed ticket rather than a
drive-by edit inside a provider-validation investigation. Recorded as a
`discovered_and_resolved_defects` item (unresolved) in the final SPRINT-008D report and as a
recommendation for SPRINT-009.

## 5. Provider fallback behavior

Documented directly from `market_data/fulfillment.py::CapabilityFulfillmentService.fulfill()`,
the one place this logic lives (screening's `live_acquisition.py` does not reimplement it):

1. For a requested capability, candidates are tried in **priority order** — by default
   (`screening.live_acquisition.build_capability_registry`), every enabled provider that declares
   the capability, sorted **alphabetically by `provider_id`**. For `earnings_calendar_v1` with
   both Alpha Vantage and Finnhub enabled, this means **Alpha Vantage is tried first, Finnhub
   second** — not the reverse.
2. On success, fulfillment returns immediately: `FULFILLED` if the first candidate succeeded,
   `DEGRADED` if an earlier candidate failed and a later one succeeded.
3. **On any failure — not only `UNSUPPORTED_CAPABILITY`** — fulfillment falls through to the next
   candidate in priority order. This includes `AUTHENTICATION_FAILED`, `ENTITLEMENT_MISSING`,
   `RATE_LIMITED`, and every other classified error. If every candidate fails, the result is
   `FAILED` with full per-provider attempt evidence retained (`ProviderFulfillmentAttempt`, never
   silently dropped).
4. Already covered by existing, passing tests, not newly added here:
   `tests/market_data/test_fulfillment.py::test_primary_failure_secondary_success_is_explicitly_degraded`
   and `::test_all_providers_fail_closed_with_aggregated_evidence`.

**Consequence for the Finnhub finding (Section 3)**: because Alpha Vantage has priority over
Finnhub for `earnings_calendar_v1`, and the fallback mechanism tries every configured provider
regardless of failure type, a Finnhub-specific entitlement problem does **not** necessarily block
`earnings_calendar` from working in actual screening use — only if Alpha Vantage is *also*
unavailable or failing would the capability fail entirely. `/ops/market-data/validate`, however,
tests each requested provider directly and independently (not through the fallback chain), which
is almost certainly how this issue was first noticed — a provider-level diagnostic failure that
may not translate into a signal-level failure at all. This is exactly why Section 3.1's live check
matters: it is the only way to know whether Alpha Vantage alone is sufficient, or whether both
paths are degraded.

## 6. Conclusion

- Provider capability routing is correct and already well-tested; no code change needed.
- Forward Factor's (and every registered signal's) actual data requirements were verified
  directly against the live adapters, surfacing one real, minor discrepancy in the public
  capabilities catalog (Section 4) — documented and recommended for a future ticket, not fixed
  here.
- Provider fallback behavior is documented precisely and is already correctly implemented and
  tested; it likely already mitigates the reported Finnhub issue's practical impact, pending
  live confirmation.
- The Finnhub authorization issue itself has a well-evidenced code-level hypothesis
  (entitlement, not authentication) but requires one Founder-run command (Section 3.1) for final
  confirmation — this agent could not obtain the live credential needed to run it directly, by
  the same secret-handling design this sprint's own ACT-001 relied on.

No code or configuration changes were made by this ticket.
