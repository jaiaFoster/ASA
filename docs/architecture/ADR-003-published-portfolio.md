# ADR-003: Persisted runs and atomic portfolio publication

Status: Accepted for ASA-FEAT-002 (2026-07-19)

## Context

Portfolio reads must never expose a partially written run or lose the last known successful result when a later synchronous run fails. The runtime remains Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, and React/TypeScript/Vite.

## Decision

Persist every execution in `runs` and its four ordered facts in `run_steps`. A successful execution normalizes one immutable `portfolio_snapshot` with broker accounts and positions. In one PostgreSQL transaction ASA inserts the snapshot graph, marks the run and publish step successful, creates a publication, and upserts the singleton row `publication_pointer(id = 1)`.

The pointer is the only canonical current-publication authority. Failed acquisition, normalization, or validation marks its run failed outside the publication transaction and never modifies the pointer. Portfolio reads join through the pointer; they do not infer currency from timestamps or the latest run.

`RunPortfolioIntelligence` executes synchronously. No worker, job registry, thread, queue, scheduler, retry framework, event bus, or alternate composition path is introduced.

## Canonical ownership

- `runs` and `run_steps`: execution history and failure evidence.
- `portfolio_snapshots`, `broker_accounts`, `equity_positions`, `option_legs`: immutable normalized portfolio facts.
- `publications`: successful run-to-snapshot publication history.
- singleton `publication_pointer`: current published portfolio.

The database constrains statuses, terminal completion, account ownership, option shape, and the one-row pointer. A deferred PostgreSQL constraint trigger rejects a publication whose run is not successful at transaction commit.

## Recovery

The migrations downgrade in reverse dependency order. A failed publication transaction rolls back all candidate snapshot rows and preserves the prior pointer. Operators can inspect the failed persisted run without changing served data.
