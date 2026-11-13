# Persistent Morning Brief Engineering Agent

This replaces a chat-only scheduled execution with a GitHub-hosted repository
checkout, Python 3.12, project dev dependencies, Codex CLI, and GitHub CLI.

## Activation (required owner steps)

1. Review and merge the implementation PR. GitHub Actions only runs workflows
   from the default branch on a schedule.
2. In repository **Settings → Secrets and variables → Actions**, create the
   repository secret **OPENAI_API_KEY**. Use a scoped/budgeted API key; a ChatGPT
   subscription does not automatically provide API billing credentials.
3. In **Settings → Actions → General → Workflow permissions**, permit the
   workflow's `GITHUB_TOKEN` to create branches, issues, and pull requests.
   Repository/org rulesets may require an explicit allowance. Do **not** grant
   automatic merge, deployment, broker credentials, or production secrets.
4. Run **Actions → Morning Brief Engineering Agent → Run workflow** once to
   verify connectivity, dependencies, issue creation, and branch/PR permissions.
   Check the workflow log. A first run processes up to 3 briefs.
5. Disable the old ChatGPT Morning Brief Engineer automation after verifying
   the GitHub Actions run, to avoid two independent workers.

## Behavior

- Schedule: daily **09:00 America/Phoenix**, implemented as 16:00 UTC (Arizona
  does not observe daylight saving time).
- Each run triages up to 3 dated Markdown briefs (manual dispatch allows 1–5).
- The agent reads the brief and existing GitHub issue catalog and proposes
  typed dispositions. The controller validates existing issue references,
  creates new issues for novel problems, and checkpoints each fully reviewed
  brief in `claude-morning-briefs/ENGINEERING_REVIEW_STATE.json`.
- The state records per-file SHA-256, issue IDs, review time, and finding count.
  If a brief changes, its hash changes and it becomes pending again.
- The historical YAML cursor remains authoritative until migration acceptance;
  the new JSON checkpoint file is a proposed v2 ledger, not an automatic
  assertion that the historical archive is fully reviewed.
- Once the backlog is exhausted, the runner selects **one** open issue with
  the `agent-ready` label per run. Apply this label only to dependency-ready,
  bounded engineering tickets that are already authorized and have no
  unresolved Founder/Architect decision.
- For issue work, Codex edits the checked-out repo, the controller runs
  `python -m pytest -q`, and only passing changes become a PR.
- The worker never merges, deploys, changes governance, or closes issues by
  itself. GitHub issue closure through `Closes #N` happens only upon an
  authorized PR merge.

## Operational caveats

- The GitHub-hosted runner is ephemeral, not a permanently running VM.
  Persistence is via GitHub issues, branches, PRs, and committed checkpoints.
- The first-run backlog has 26 dated briefs; at 3/run, intake takes at least
  nine successful daily runs unless manually dispatched more often.
- If the agent creates an issue but the run fails before pushing its
  checkpoint PR, review and deduplicate that issue before retrying.
- If the checkpoint PR remains unmerged, later runs on `main` can reprocess
  those same briefs. **Merge each approved checkpoint PR before the next
  scheduled run**. A durable state branch/issue store or dedicated database
  would be needed for safe unattended continuation without reviews.
- This automation does not have authority to implement unapproved
  architecture changes or Founder-only decisions. Such work stays in issues.
- Cost: GitHub Actions minutes plus Codex API token usage. Budget accordingly.
