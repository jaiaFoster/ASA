# Railway deployment observer

The Railway Deployment Observer copies a bounded, redacted diagnostic snapshot into a
14-day GitHub Actions artifact and publishes a concise report to the pull request associated
with the deployed commit. The artifact remains the immutable diagnostic archive; the marked
pull request comment is the review surface and is updated on reruns. Railway remains
authoritative for deployment state and complete logs. The observer is read-only: it lists
deployments and reads build/runtime logs; it cannot deploy, restart, roll back, change
variables, or alter Railway resources.

## Founder setup

1. In Railway, create a project-scoped token that can read historical deployments and build
   and runtime logs for the ASA project. Do not use an account-wide token.
2. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name the secret `RAILWAY_TOKEN` and paste the project token. Do not add Railway variables
   or credentials as GitHub variables.
4. Open **Actions → Railway Deployment Observer → Run workflow**. Enter a known Railway
   deployment ID, leave runtime logs enabled, and run it.
5. Confirm the job summary identifies the production deployment and download the
   `railway-deployment-<deployment-id>` artifact. It must contain `manifest.json`,
   `build-log.jsonl`, `runtime-log.jsonl`, and `summary.md`.
6. Seed a non-production diagnostic message containing test credentials, if available, and
   confirm the artifact contains `[REDACTED]` rather than the seeded value. Never seed a real
   credential for this check.

Every `deployment_status` event starts the observer, including events with differently cased or
missing GitHub environment metadata. Manual runs also remain fixed to the production Railway
environment and cannot override it. If a GitHub deployment payload contains a Railway
deployment ID under
`payload.railway_deployment_id`, `payload.railwayDeploymentId`, `payload.deployment_id`, or a
nested `payload.railway` deployment ID, that ID is used. A Railway deployment ID in the `id`
query parameter of the deployment status target URL is next. Only when none of those sources
provides an ID does the observer list deployments and select the latest ASA production deployment.
Resolved IDs are polled using the explicit production service and environment until Railway
reaches a terminal state or the bounded deadline, then build and runtime logs are collected.

## Pull request reports

After collection, the observer resolves pull requests associated with the deployed commit SHA
using GitHub commit metadata. It prefers an exact merge-commit match merged into the default
branch and never guesses from a source branch name. One unambiguous association receives a
`Railway Deployment Report` comment containing component statuses, the decisive root-cause
excerpt, bounded collapsible logs, and links to the workflow run and its artifact area.

The comment begins with `<!-- ASA_RAILWAY_DEPLOYMENT_OBSERVER -->`. Reruns search all issue
comments for that marker and update the existing report instead of adding another. If GitHub
reports no pull request or multiple ambiguous candidates, publication is skipped without
failing artifact collection. Resolution and comment outcomes are stored in `manifest.json`.

Comment text receives the same redaction as artifacts and tighter limits: 20 root-cause lines,
100 build lines, 150 runtime lines, 100 health-check lines, and fewer than 50,000 total
characters. Raw environment variables and complete GitHub event payloads are never included.
Comment and artifact publication are independent `always()` steps; the final workflow step
reports partial completion if collection, comment publication, or artifact upload fails.

## Reading an artifact

The manifest records deployment identity, status, commit SHA, bounded line counts, collection
status, and redaction count. The summary uses deterministic keyword rules to identify the first
bounded error cluster and likely build, pre-deploy, startup, healthcheck, or runtime phase. It
quotes at most 80 redacted log lines. No external AI service is called.

An empty log stream produces an empty JSONL file. If collection, parsing, or redaction fails,
the collector deletes partial output and writes only `failure.json` and a safe `summary.md`.
Railway command failures record only the command category, exit code, and redacted stdout/stderr,
bounded together to 100 lines or 16 KiB. The token and process environment are never serialized.
Raw logs are never uploaded or committed.

## Rollback

1. Disable the **Railway Deployment Observer** workflow in the GitHub Actions UI to stop new
   automatic and manual observations immediately.
2. Delete the `RAILWAY_TOKEN` repository secret.
3. Revoke the project-scoped token in Railway.
4. Delete existing observer artifacts from their workflow runs if early removal is required;
   otherwise GitHub expires them after 14 days.
5. Revert the observer commit in GitHub if the workflow and tooling should be removed. Do not
   change Railway service configuration or deploy ASA as part of rollback.
