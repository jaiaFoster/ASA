# Market Data Provider Diagnostics Runbook

This runbook governs bounded, read-only provider diagnostics. Unit and contract tests remain
network-free. Never paste credentials into a command, ticket, pull request, report, or chat; place
them only in the authorized development environment under the documented `ASA_*` variable name.

## 1. Preflight

1. Confirm the provider account, subscription, and intended environment with the Founder.
2. Confirm only the variable **name**, never its value:
   `ASA_TRADIER_ACCESS_TOKEN`, `ASA_TRADIER_ENV`, `ASA_FINNHUB_API_KEY`, or
   `ASA_ALPHA_VANTAGE_API_KEY`.
3. Run the network-free platform checks:

   ```text
   PYTHONPATH=. .venv/bin/pytest -q tests/market_data
   PYTHONPATH=. .venv/bin/python -m market_data.documentation
   ```

4. Inspect the generated page under `docs/providers/` for capabilities and limitations.

## 2. Build the request plan first

Invoke `market_data.validation.command_main` through the authorized application composition with
these arguments:

```text
--provider <provider-id> [--capability <canonical-capability>]
```

Omitting `--execute` is always a dry run. Record the displayed provider, capabilities, endpoint
classes, and total request ceiling. The default ceiling is at most 12 requests per provider run,
3 per capability, one retry, 10 seconds per request, and concurrency 1. No command-line argument
may raise these ceilings.

For execution, add both explicit controls:

```text
--provider <provider-id> --capability <capability> --execute --allow-live
```

The worker environment may execute this after the dry-run plan is inspected; no interactive
confirmation is required. Never enable `ASA_LIVE_PROVIDER_VALIDATION=1` in normal PR CI.

## 3. Safe diagnostic sequence

Run one provider and one capability first. Stop on authentication, authorization, or entitlement
failure; repeated calls cannot repair those conditions.

1. `deterministic_fixture`: validate the offline workflow and report rendering.
2. Provider quote or smallest supported read: distinguish credentials from transport failure.
3. Requested capability: inspect semantic status, schema, freshness, latency, and quota metadata.
4. Expand to another capability only while the displayed validation budget remains available.

Every request must have a budget authorization. Retries consume budget. Never loop, run concurrent
probes, broaden symbol lists, or retry after quota exhaustion.

## 4. Interpreting normalized failures

| Result | Meaning | Action |
|---|---|---|
| `configuration_error` | Required local configuration is absent or invalid | Correct the named configuration category; never print its value |
| `authentication_failed` | Credential was rejected | Stop; Founder verifies account/credential outside repository channels |
| `authorization_failed` / `entitlement_missing` | Identity is known but capability is not permitted | Stop; record plan/entitlement blocker |
| `invalid_request` | Provider rejected safe request parameters | Compare endpoint class and canonical projection with official documentation |
| `unsupported_symbol` | Address is valid but unavailable for the subject | Verify canonical subject and explicit projection; do not infer another symbol |
| `no_data` | Provider explicitly reported no data | Check symbol, range, resolution, market session, and entitlement |
| `empty_payload` | Successful transport contained no usable rows | Treat as failure; do not report success |
| `schema_mismatch` | Shape or array consistency changed | Preserve bounded schema evidence and stop that capability |
| `rate_limited` / `quota_exhausted` | Provider or local budget refused more work | Stop and honor cooldown; do not raise the ceiling |
| `timeout` / `transport_error` | Read did not complete | Use at most the authorized retry, then record external blocker |
| `provider_unavailable` | Provider service failed | Preserve last successful snapshot; do not silently substitute |

## 5. Finnhub daily-candle diagnosis

Use only SPY and AAPL, resolution `D`, then a recent short and medium UTC epoch range. For each
bounded attempt record:

- credential acceptance and HTTP status category;
- start timestamp less than end timestamp;
- provider status field (`ok` or `no_data`);
- non-empty, equal-length `o`, `h`, `l`, `c`, `v`, and `t` arrays;
- UTC timestamp conversion and freshness;
- entitlement/plan diagnostic and observed quota state.

HTTP 200 alone is never success. `s=no_data` is `no_data`; empty arrays are `empty_payload`;
different array lengths are `schema_mismatch`. Classify the likely cause as configuration, request
parameters, symbol, time range, resolution, entitlement, rate limit, provider availability, local
transport, or inconclusive. Do not run a high-volume probe.

## 6. Safe retry and artifact handling

- Retry only errors marked retryable and only within the pre-authorized retry count.
- Do not retry authentication, authorization, entitlement, schema, empty-payload, or no-data
  failures automatically.
- Retain only rendered secret-free reports and bounded request accounting.
- Never retain raw payloads, full URLs, headers, environment dumps, cookies, tokens, or passwords.

## 7. Escalation template

```yaml
provider: <provider-id>
capability: <canonical-capability>
environment: <sandbox-or-production-name-only>
validation_time_UTC: <timestamp>
request_count: <bounded-integer>
endpoint_class: <safe-endpoint-class>
HTTP_status_category: <2xx-4xx-5xx-or-transport>
normalized_failure_category: <provider-neutral-code>
entitlement_status: <known-unknown-blocked>
quota_status: <safe-observed-summary>
response_schema_status: <valid-invalid-inconclusive>
freshness_status: <fresh-stale-unknown>
likely_cause: <bounded-summary>
recommended_Founder_action: <specific-action-or-none>
evidence_artifact_paths:
  - <secret-free-relative-path>
```

Prohibited fields: access token, API key, authorization header, password, cookie, session, raw
response, full GitHub event, environment dump, or secret-bearing URL.
