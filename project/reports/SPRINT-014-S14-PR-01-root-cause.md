# SPRINT-014 S14-PR-01 — Root-Cause Evidence Packet

Scope per ticket: reproduce and evidence the root cause, no production behavior change. All evidence below is either a direct code citation on current `main` or a new, passing test. No instrumentation was added to production code; the one new test is disposable per the ticket's own rollback note.

## 1. Call graph (composition root -> provider)

```text
asa/scheduled_screening.py::run_scheduled_refresh
  -> build_shared_market_data_access()            # one CapabilityFulfillmentService per unique SYMBOL in the cycle
  -> per (strategy_id, symbol) pair:
       screening/live_adapters.py::LIVE_ADAPTER_FACTORIES[strategy_id](symbol, fulfillment)
         -> _acquire_or_raise() / _acquire_combined_chain() / _acquire_daily_closes()  # imperative, strategy-authored sequence
              -> screening.live_acquisition.acquire_capability()
                   -> market_data/fulfillment.py::CapabilityFulfillmentService.fulfill(request)
                        -> provider(s) in priority order
```

There is no step between "per-pair adapter" and "fulfillment service" that declares a subject's full data requirement up front. Each adapter is a hand-written sequence of `_acquire_or_raise` calls; the "plan" only exists implicitly, as whatever that Python function happens to execute, in whatever order, for that one strategy.

## 2. Confirmed: exact-request caching exists; subject-first planning does not

`CapabilityFulfillmentService._results` (`market_data/fulfillment.py:130`) is a `dict[tuple[CapabilityRequest, bool], CapabilityFulfillmentResult]`. A `fulfill()` call is served from cache **only** when a later caller constructs a `CapabilityRequest` that is exactly, structurally equal to an earlier one (`market_data/fulfillment.py:133-142`). This is real and correct as far as it goes (SPRINT-013 S13-03B) — but it is a side effect of two callers happening to build byte-identical requests, never the result of a shared, subject-owned plan deciding once what a subject needs. Nothing computes "AAPL needs: EARNINGS_CALENDAR_V1, REAL_TIME_QUOTE_V1, OPTION_CHAIN_V1{front}, OPTION_CHAIN_V1{back}, HISTORICAL_BARS_V1" as one upfront union — each strategy adapter discovers and requests its own needs step by step, at evaluation time.

## 3. Confirmed: strategy-facing code holds live acquisition objects (I-09 currently violated)

```
$ grep -rl "CapabilityFulfillmentService\|RequestBudgetManager\|from market_data.fulfillment\|from market_data.budget" strategies/ strategy_runtime/ screening/
strategy_runtime/service.py
strategy_runtime/execution.py
strategy_runtime/__init__.py
strategy_runtime/market_data_planning.py
strategy_runtime/context.py
screening/live_acquisition.py
screening/cli.py
screening/live_adapters.py
screening/live_context.py
```

`strategy_runtime/context.py:32` — `RuntimeContext.fulfillment: CapabilityFulfillmentService | None`. Strategy-facing runtime context directly carries a live fulfillment object today. Target invariant I-09 ("Strategy-facing code receives no provider, transport, budget, or fulfillment object") is not yet satisfied anywhere in the current live path.

## 4. Confirmed: the sealed-snapshot and canonical-fact layers already exist and are unused

`market_data/snapshot.py` (`MarketSnapshot`, 269 lines) and `facts/repository.py` (`InMemoryCanonicalFactRepository`, append-only, versioned) both already exist, matching `architecture/ASA-ARCH-007-Market-Data-Platform.md`'s frozen contracts. Neither has a single live caller:

```
$ grep -rl "from market_data.snapshot\|from market_data.replay" --include=*.py . | grep -v tests
market_data/__init__.py
market_data/replay.py
$ grep -rl "from facts" --include=*.py . | grep -v tests
facts/__init__.py
facts/repository.py
```

Zero references from `asa/`, `screening/`, or `strategy_runtime/`. The sealed-evidence boundary and canonical-fact layer are architecturally accepted and already built — they were simply never wired into the live scheduled path, which acquires directly through per-strategy adapters instead.

## 5. Confirmed: no durable shared failure history (repeated-failure behavior)

`market_data/fulfillment.py:143-147`, on a cached result that is `FulfillmentStatus.FAILED`:

```python
# A failed attempt is never served from cache, regardless of
# why: it always gets its own fresh, independently isolated
# retry rather than propagating one evaluation's failure onto
# every later evaluation that shares this service.
del self._results[key]
```

This is a deliberate, correct design for **failure isolation** within one cycle (SPRINT-013 S13-03B) — but it means the current mechanism has no concept of "this datum is UNKNOWN for this cycle, shared by every consumer." Every consumer that needs the same failing datum pays its own full provider round-trip.

**New test, deterministic (not calendar-luck-dependent), `tests/asa/test_scheduled_screening.py::test_a_failed_shared_capability_gets_its_own_independent_retry_not_a_shared_known_failure`:**

Two `skew_momentum` pairs share one symbol (AAPL) in one cycle. The historical-bars response is forced to Tradier's documented empty shape for both, so the `HISTORICAL_BARS_V1` capability fails deterministically for both pairs regardless of run date.

Result: `outcomes[0].request_count == 4` (nothing cached yet), `outcomes[1].request_count == 1` (quote/expirations/chain reuse for free; the failed history capability alone is retried fresh). If a shared negative result existed, the second pair's count would be `0`, not `1`. Passing, confirmed on current `main` before any SPRINT-014 code change:

```
tests/asa/test_scheduled_screening.py::test_a_failed_shared_capability_gets_its_own_independent_retry_not_a_shared_known_failure PASSED
37 passed  (full tests/asa/test_scheduled_screening.py + tests/market_data/test_fulfillment.py)
```

This is the same mechanism S13-08's audit (`project/reports/SPRINT-013-S13-08-audit.md`, finding #2) already flagged as `UNKNOWN_REQUIRES_ARCHITECT_OR_FOUNDER` and left as an open blocker — SPRINT-014 is the authorized resolution path for that blocker.

## 6. Order-independence: holds for identical requests, not for a real union

`test_a_symbol_shared_across_two_pairs_in_one_cycle_reuses_the_first_pairs_requests` and `test_different_symbols_in_the_same_cycle_never_share_requests` (both pre-existing, unmodified) show reuse is correct and order-independent **when two adapter invocations happen to construct byte-identical `CapabilityRequest`s**. Nothing in the current design generalizes this to two *different* but overlapping requirements (e.g., a different `required_fields` projection, or a second strategy needing the same quote under a different freshness policy) — those would simply be two independent fresh requests, because there is no subject-level union step to notice the overlap in the first place. This is the gap PR-03's "union exact field, window, and expiration demand" step exists to close.

## 7. Distinguishing exact-request caching from subject-first planning (summary)

| Property | Exists today? | Owner |
|---|---|---|
| Two byte-identical requests within one cycle reuse | Yes | `CapabilityFulfillmentService._results` |
| A subject's full data requirement is declared once, up front | No | none — implicit in each adapter's own code |
| Calls depend on unique required data, not strategy count/order (I-02) | Only incidentally, for identical requests | none |
| A known failure is shared across consumers in one cycle | No | none (deliberately evicted, see §5) |
| Sealed, replayable evidence envelope per cycle (I-06, I-11) | Contract exists (`market_data/snapshot.py`), unused live | none wired |
| Named, versioned, compute-once derived facts (I-07, I-08) | `analytics/` computes ad hoc per adapter call, not materialized once per snapshot | none wired |

## Conclusion

Confirmed on current `main` (`docs/sprints/SPRINT-014.yaml` activation commit `04ab740`): production acquisition is strategy-driven, not subject-first. Exact-request success caching (S13-03B) measurably reduces duplicate calls for identical requests but is not a substitute for a subject-owned plan, sealed evidence boundary, or shared failure history — all three are absent from the live path today, and the standing S13-08 blocker (finding #2) is the same underlying gap. This matches SPRINT-014's `root_cause.statement` exactly; no revision to that statement is needed.

**Verdict: ROOT_CAUSE_ACCEPTED** (pending independent Architect confirmation per `per_pr_gate`).
