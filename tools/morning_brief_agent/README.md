# Morning Brief Intake — no separate AI API billing

This GitHub Actions workflow runs daily at **09:00 America/Phoenix** and uses
only the built-in GitHub Actions `GITHUB_TOKEN` and Python standard library.

## What works unattended

- Checks out the real repository and reads dated Markdown briefs.
- Enqueues up to three new/changed briefs per run as GitHub Issues.
- Stores a per-brief SHA-256 marker in each issue body, so repeat runs skip
  already-enqueued content, even if the issue is closed.
- Runs on GitHub-hosted infrastructure without OpenAI/Anthropic API credentials.
- Existing repository CI can run regression tests when an engineering PR is
  subsequently opened.

## What does NOT work unattended

This workflow **does not** perform AI engineering analysis, deduplicate
semantic findings, change application code, run an AI coding agent, or advance
`ENGINEERING_REVIEW_CURSOR.yaml`. It creates a durable review queue; a
ChatGPT or Claude subscription is not an API credential for unattended
GitHub-hosted AI execution.

The existing ChatGPT automation can review these queued briefs using GitHub
tools, map observations to canonical issues, and prepare PRs when its execution
environment supports the task. Its runs are bounded and cannot be assumed to
have a persistent checkout or test runner. A Claude Code subscription may
support interactive or scheduled local use subject to Claude's current plan
and product capabilities; do not assume it can be triggered remotely without
an authenticated service and an always-on host.

## Activation

1. Review and merge this PR; scheduled workflows run from the default branch.
2. In GitHub repository Settings → Actions → General, ensure `GITHUB_TOKEN`
   can create issues (and organization policies permit workflow execution).
3. Manually dispatch **Morning Brief Intake (no AI API)** once and verify
   that it creates three source-review issues and does not duplicate them
   on a second run.
4. Keep the ChatGPT engineering automation for actual review; avoid having it
   independently create duplicate per-brief intake tickets.

## Important design distinction

GitHub Issues created by this workflow are **intake tickets**, not proof that
all problems in a brief have been identified. The engineering-review cursor
must advance only after the actual analysis and disposition work is done.

A future fully unattended coding agent requires one of:
- a provider-hosted coding agent entitlement/integration;
- a locally hosted agent with a scheduled machine and permitted subscription
  authentication; or
- a separately billed AI API.

No automatic merges or deployments are authorized.
