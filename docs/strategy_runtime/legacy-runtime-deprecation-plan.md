# Legacy screening-state retirement

LEGACY-001 completes the cold-start cutover to the universal runtime.

## Canonical authority

`universal_screening_state` is the only latest-result table. Both the API
refresh endpoint and `python -m asa.scheduled_screening` write through
`strategy_runtime.service` and `PostgresLatestResultRepository`. Read endpoints
query that same repository and never execute providers.

The capability endpoint is projected from the registered universal
`StrategyContract` instances. The retired screening registry is not a second
catalog authority for the deployed application.

## No backfill

Migration `0007` drops `screening_state`. It does not translate or copy old
rows. After upgrade, existing rows in `universal_screening_state` remain
available. On a new or empty universal cache, the next successful scheduled
run or bounded refresh naturally repopulates latest state.

## Rollback

Downgrading `0007` recreates the old table schema empty. Dropped legacy rows
cannot be recovered by Alembic. Before operational rollback, retain a normal
database backup if those obsolete rows matter. Application rollback may write
new legacy rows after the schema is recreated; no dual-read or dual-write
compatibility path exists.
