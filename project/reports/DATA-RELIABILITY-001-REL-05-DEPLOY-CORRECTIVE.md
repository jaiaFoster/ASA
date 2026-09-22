# REL-05 production verification corrective

Authorized deployment of `main@b366657dea25341b0fc614c1ca1a780b21996194`
failed before application startup. Railway deployment
`f91b0692-9109-49e9-80e4-e275ed57a1c4` built successfully, but Railpack 0.39
executed the unqualified deploy command with its Mise system Python. Runtime
then failed with `No module named alembic`; the application and census never
ran.

The build manifest proves dependencies were installed into `/app/.venv`.
`railway.json` now invokes that exact interpreter for migration and Uvicorn.
This is the smallest configuration-owner correction: no application,
provider, strategy, database schema, or research semantics changed.
