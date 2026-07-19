# ADR-002: Single composition root

Status: Accepted for ASA-PROD-001 (2026-07-19)

## Decision

`backend/src/asa/bootstrap.py::build_application(settings, overrides)` is the one production composition root. It selects the configured provider, constructs the SQLAlchemy engine and PostgreSQL repository, wires the application use case, and supplies those dependencies to FastAPI routes.

Application and domain modules own interfaces and rules but instantiate no infrastructure. API routes and React contain no business rules. Tests replace ports only through `DependencyOverrides` passed to `build_application`; active dependencies are exposed through `app.state` solely for composition evidence.

The executable module calls the composition root and hands the resulting ASGI application to Uvicorn. It does not construct dependencies independently.

## Invariants

- No module-level application dependencies.
- Provider implementation imports live only below `asa.integrations`.
- GET reads the repository and never invokes the provider.
- PostgreSQL is the only production persistence implementation.
- Dependency selection is static and explicit; there is no plugin loading.
