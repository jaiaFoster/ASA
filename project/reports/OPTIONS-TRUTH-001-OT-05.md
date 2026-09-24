# OPTIONS-TRUTH-001 — OT-05 shared-query proof

Baseline: `main@2d15c424528a892d94ae7a6a73ce9fe0e19ba3ee`  
Operational issue: [#463](https://github.com/jaiaFoster/ASA/issues/463)

## Production declaration proof

At one fixed subject/cycle time, the three current option consumers declare 10
bootstrap demands but only 5 unique demand identities:

- real-time quote: one identity shared by all three;
- option-chain discovery: one identity shared by all three;
- earnings calendar: one identity shared by Forward Factor and Earnings
  Calendar;
- historical bars: two distinct identities because the declared windows and
  evidence needs are genuinely different.

Registration order leaves the demand multiset unchanged. `run_subject_plan`
unions by deterministic demand identity, and one `SubjectAcquisitionPlan` per
subject resolves each unique request once.

## Success and failure reuse evidence

- `tests/screening/test_subject_planning.py::TestOrderAndCountIndependence`:
  two consumers of one successful demand produce one fulfillment call in both
  registration orders.
- `tests/screening/test_subject_planning.py::TestSharedExhaustedFailure`:
  two consumers of one failed demand share the identical exhausted result and
  pay one fulfillment call.
- `tests/market_data/test_subject_plan.py::test_a_reused_result_does_not_duplicate_attempt_rows`:
  reuse does not fabricate a second durable attempt.
- `tests/strategy_runtime/test_orchestration.py::TestSharedPlanWithLegacyEarnings`:
  subject-first and compatibility consumers share the same underlying plan,
  including exhausted failure.
- `tests/strategy_runtime/test_options_shared_query.py` pins the exact current
  production option declarations and order independence.

## Result

No correction was required. Provider calls remain one per unique eligible
request (plus the plan's bounded retry for a retryable failure), never one per
strategy consumer. No cache, provider, persistence, or strategy-specific
orchestration path was added.
