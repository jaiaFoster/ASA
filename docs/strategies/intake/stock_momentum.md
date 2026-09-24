# Intake decision: `stock_momentum` (SL-03) — SKIP for this wave

Source: `jaiaFoster/Stonk@5f3fec846f70e9739cf3f15695fd587f0604344c`,
`app/services/stock_momentum_strategy_service.py` (the repository's only
remaining source-documented stock strategy; the migrated
`asa.stonk.stock_momentum` manifest is a score shell that does not carry these
rules).

## Why it cannot be implemented faithfully now

The source's material semantics depend on inputs outside ASA's market-data
authority or owned by other ASA layers:

| Source rule | Location | Obstacle |
|---|---|---|
| Score and blocker use current holding and single-name allocation (≥ 15% blocks) | `_score_ticker`, `_entry_quality_gate` L281 | portfolio policy belongs to ASA's Portfolio Engine (inventory, "Important behavioral findings") |
| +6 for a hardcoded macro "growth bucket" ticker list; −4 for a hardcoded speculative list | `TECH_BUCKET_TICKERS`, `SPECULATIVE_TICKERS` | discretionary ticker lists, not a methodology |
| +5 when the legacy portfolio-gap engine flags the ticker | `_gap_suggestions_by_ticker` | legacy engine not migrated |
| +3 when "relevant news" exists | `news_items` | no news capability; relevance undefined |
| Universe = holdings + watchlist | `build_stock_momentum_strategy` | user-specific universe, not the S&P active universe |

Dropping these rules would change the strategy's verdicts: a
"silent structure/semantics substitution" the program forbids.
Per STRATEGY-LIBRARY-001 ("If repository/source evidence does not uniquely
define a strategy's material semantics, skip that candidate"), it is skipped.
This is not a Founder blocker: it is not uniquely necessary to the product,
because B001 already proves the stock path.

## Reconsider when

A Portfolio Engine exposure input and a documented replacement for the
theme/news/gap bonuses exist, or a Founder-specified variant defines them.
