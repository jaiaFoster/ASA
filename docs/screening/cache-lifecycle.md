# Universal screening latest-state lifecycle

`universal_screening_state` is the one latest-result cache and canonical
screening read model. It holds at most one result per `(signal_id, symbol)`.
Successful writes use upsert semantics. Runs never erase untouched pairs.

Reads are provider-free. State changes only through the scheduled screening
entrypoint, another direct universal runtime caller, or the explicit bounded
refresh endpoint.

Opportunity evolution is separate append-only evidence in
`opportunity_observation_history`; it does not compete with latest state.

The public `age_seconds` field exposes exact age. The screening surface also
offers a documented 24-hour generic display classification. This is not an
investment or strategy freshness rule.

The legacy `screening_state` table was dropped without backfill by migration
`0007`. An empty universal cache is repopulated by a fresh successful run.
