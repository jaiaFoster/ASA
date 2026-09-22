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

## Production follow-up

Deployment of `main@50a5e3802d17eb6ac46ea0bb4440866ab7eec25d`
proved a second Railpack boundary defect. The build plan reported that
`/app/.venv` was created and copied into the final image, but the deployed
container did not contain `/app/.venv/bin/python`. ASA now uses a bounded
repository Dockerfile so dependency installation, migration, and Uvicorn all
use one deterministic Python 3.12.13 runtime. No application, provider, or
strategy behavior changes.
