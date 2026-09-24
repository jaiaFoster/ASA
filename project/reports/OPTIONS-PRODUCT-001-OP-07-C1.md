# OPTIONS-PRODUCT-001 — OP-07-C1 truthful card economics

Baseline: `main@9e12520`
Operational issue: [#481](https://github.com/jaiaFoster/ASA/issues/481)
Found by: OP-07 production observation (`main@d6d4c8d`)

## Root cause

The trade card's capital, maximum loss, maximum profit and breakeven rows read
only from the canonical `OptionTradeProposal`. Every projection of that
proposal (the trade-proposal API and OP-06 tracking) built it without a payoff
model, so all four quantities were `unknown: payoff_model_not_attached`. This
was true for **every** structure, including verticals, even though the
deterministic terminal payoff already computes their bounds.

## Correction

- `build_option_trade_proposal` derives the deterministic terminal payoff from
  the same exact legs when none is supplied. Its bounds depend only on exact
  strikes and the modeled entry, not on the display grid, so the API and
  tracking projections agree. It records
  `payoff_model:exact-leg-terminal-payoff-v1`.
- `strategy_runtime/option_payoff.same_strike_calendar_loss_bound` adds the one
  model-independent calendar fact. For a long same-strike, same-type,
  equal-quantity calendar opened at a modeled debit, loss is bounded by that
  debit × multiplier: the later-dated long leg, assumed exercisable
  (American-style listed equity option), is always worth at least the short
  leg's obligation. The proposal marks the bound
  `maximum_loss_model:same-strike-calendar-debit-bound-v1` with three explicit
  assumptions: the long leg is American-style; it is exercised or closed
  promptly on assignment; and the bound **excludes a dividend owed after an
  early call assignment before an ex-date**. A matching risk note, which also
  mentions temporary stock-level assignment margin, is rendered on the card.
- The trade card now shows the typed reason behind every non-supported
  quantity and lists the proposal's model assumptions.
- For calendars, maximum profit and breakeven stay `unknown:
  later_expiring_leg_value_is_model_dependent`. Credit entries, unresolved
  structures and any non-matching shape receive no bound. The resolver already
  refuses a diagonal as a calendar.

Pinned vectors:

| Structure | Max loss | Capital | Max profit | Breakeven |
|---|---|---|---|---|
| 100/110 call vertical, debit 4.00 | 400.00 | 400.00 | 600.00 | 104 |
| same-strike 200 call calendar, debit 2.10 | 210.00 (bound) | 210.00 | unknown | unknown |

Observed production calendar PSX (debit 8.0) would now render maximum loss
and capital required of 800.00.

## Independent review

The independent financial/code review found the code correct. It requested
one change, now applied: disclose the dividend-on-early-call-assignment
exception, the prompt-exercise requirement and assignment margin. At its
request, tests now cover a put calendar, quantity scaling, reversed/same-
expiration/unequal/diagonal/mixed-type/zero-debit negatives, grid
independence, and the bound persisting into the tracked proposal.

## Boundaries

This change is presentation-contract financial truth, owned by the payoff
layer. It does not change signals, strategies, gates, acquisition or broker
behavior, and it makes no return or fill claim.
