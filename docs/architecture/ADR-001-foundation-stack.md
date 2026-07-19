# ADR-001: Foundation stack

Status: Accepted for ASA-PROD-001 (2026-07-19)

## Context

ASA needs its first production-shaped market-data slice without inheriting the legacy Stonk topology. The slice requires a typed HTTP contract, one relational source of truth, migrations, and a separately testable browser UI.

## Decision

Use FastAPI and Pydantic for HTTP boundaries, SQLAlchemy with psycopg for PostgreSQL access, Alembic for schema migrations, and React with TypeScript and Vite for presentation. Standard pip-compatible `pyproject.toml` tooling and npm lockfiles make local and CI builds reproducible.

PostgreSQL owns canonical observations. The provider is deterministic and local; no credential or external-provider health semantics exist in this slice. React renders fields received from the API and contains no freshness, pricing, or provider-selection logic.

## Alternatives

- The legacy Flask/SQLite topology was rejected by ticket constraint and because it couples runtime, cache, and presentation concerns.
- Async database access was deferred: this single-symbol slice has no concurrency requirement that justifies a second execution model.
- A background ingestion process was excluded. The development-only POST endpoint makes slice verification explicit.

## Consequences

The schema is migration-owned and reversible. Adding a live provider, authentication, scheduling, or deployment requires a new ticket and architecture review.
