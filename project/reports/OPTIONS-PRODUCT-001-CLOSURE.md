# OPTIONS-PRODUCT-001 — closure

State: `CLOSED`
Final production SHA observed: `7566f4fb05d6113824e6e64cee816463e6b2841d`
(verified via `/api/v1/version`)

## Merged implementation

| Ticket | PR | Outcome |
|---|---|---|
| OP-01 | #469 | canonical provider-neutral trade proposal contract |
| OP-02 | #471 | exact-leg deterministic payoff model with pinned vectors |
| OP-03 | #473 | user-first trade card |
| OP-04 | #475 | payoff visualization with textual values |
| OP-05 | #477 | typed failure experience; signal ≠ executable trade |
| OP-06 | #479 | non-broker-mutating Track This on immutable proposals |
| OP-07 | #482 | Founder-utility observation on production (`d6d4c8d`) |
| OP-07-C1 | #483 | truthful card economics (deterministic bounds; same-strike calendar debit bound with disclosed assumptions), independently reviewed |

## Observation

- `d6d4c8d`, 16:24Z: 8 qualifying option results → 5 complete trade cards,
  3 typed failures, 0 defects. The production UI was rendered headlessly.
- `7566f4f`, 17:02Z ([`OPTIONS-PRODUCT-001-OP-07-C1.json`](OPTIONS-PRODUCT-001-OP-07-C1.json)):
  7 qualifying option results → 4 complete trade cards (earnings_calendar
  CI, PCG, PPG, PSX), 3 typed failures, 0 defects. The qualifying set rotated
  with the scheduled refresh: CI entered, and GILD and ICE left.
- A direct trade-proposal check at about 17:01Z on the same SHA showed the
  calendar cards' capital required and maximum loss equal to the debit bound:
  PSX 800.00, GILD 362.50, ICE 335.00, PCG 36.00, PPG 222.50. Maximum profit
  and breakeven carried the typed reason
  `later_expiring_leg_value_is_model_dependent`.

## Acceptance

A user can open an actionable option result and determine the exact intended
trade, with bounded economics where they are mathematically supportable,
without another analytical application. Uncertainty is explicit, full
evidence drill-down is retained, and there are no broker mutations,
invented returns, or duplicated acquisition.

## Known limitations

- Exercise style is not in the domain model. The calendar bound assumes
  American-style listed equity options and says so.
- Pre-expiration modeled P&L for calendars still requires explicit
  volatility assumptions from the user (OP-02 model). It is not rendered by
  default.

Any later falsifying observation reopens this sprint per the program rule.
