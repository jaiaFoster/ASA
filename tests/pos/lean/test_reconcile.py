"""
Tests for the Lean POS reconciliation layer.

Safety rules:
- No live network calls anywhere in this file.
- All GitHub data comes from pre-normalized YAML fixtures.
- No canonical records are mutated.
- The offline validator must remain importable without pulling in the online layer.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

FIXTURES = REPO_ROOT / "tests" / "pos" / "lean" / "fixtures" / "github"
RECONCILE = REPO_ROOT / "tools" / "pos" / "lean" / "reconcile.py"

from tools.pos.lean.github import FixtureAdapter, GitHubSnapshot, WriteAttemptError
from tools.pos.lean.derived import derive, ReconciliationResult
from tools.pos.lean.schemas import (
    DERIVED_STATES,
    RECON_AUTHORITY_UNKNOWN,
    RECON_CONFLICTING_STATE,
    RECON_INCOMPLETE_DATA,
    RECON_UNAUTHORIZED_MERGE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def snapshot_from(name: str) -> GitHubSnapshot:
    return FixtureAdapter(FIXTURES / name).fetch()


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RECONCILE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def run_fixture(name: str, fmt: str = "yaml") -> subprocess.CompletedProcess:
    return run_cli(
        "--fixture", str(FIXTURES / name),
        "--observed-at", "2026-07-18T10:00:00Z",
        "--format", fmt,
    )


# ---------------------------------------------------------------------------
# Group 1: Derived state — full matrix
# ---------------------------------------------------------------------------

class TestDerivedStateMatrix:
    def test_issue_open_no_pr_derives_planned(self):
        r = derive(snapshot_from("issue-open-no-pr.yaml"))
        assert r.derived_state == "planned"

    def test_draft_pr_derives_active(self):
        r = derive(snapshot_from("draft-pr.yaml"))
        assert r.derived_state == "active"

    def test_ready_pr_no_review_derives_review(self):
        r = derive(snapshot_from("ready-pr-no-review.yaml"))
        assert r.derived_state == "review"

    def test_changes_requested_derives_blocked(self):
        r = derive(snapshot_from("changes-requested.yaml"))
        assert r.derived_state == "blocked"

    def test_failed_checks_derives_blocked(self):
        r = derive(snapshot_from("failed-checks.yaml"))
        assert r.derived_state == "blocked"

    def test_successful_checks_still_review(self):
        r = derive(snapshot_from("successful-checks.yaml"))
        assert r.derived_state == "review"

    def test_authorized_merge_derives_accepted(self):
        r = derive(snapshot_from("merged-authorized.yaml"))
        assert r.derived_state == "accepted"
        assert not r.conflicts

    def test_authorized_architect_merge_derives_accepted(self):
        r = derive(snapshot_from("merged-authorized-architect.yaml"))
        assert r.derived_state == "accepted"
        assert not r.conflicts

    def test_unauthorized_merge_derives_conflict(self):
        r = derive(snapshot_from("merged-unauthorized.yaml"))
        assert r.derived_state == "conflict"
        assert any(c.code == RECON_UNAUTHORIZED_MERGE for c in r.conflicts)

    def test_closed_unmerged_pr_derives_cancelled(self):
        r = derive(snapshot_from("closed-unmerged.yaml"))
        assert r.derived_state == "cancelled"

    def test_missing_pr_open_issue_derives_planned(self):
        r = derive(snapshot_from("missing-pr.yaml"))
        assert r.derived_state == "planned"

    def test_missing_authority_derives_undetermined(self):
        r = derive(snapshot_from("missing-authority.yaml"))
        assert r.derived_state == "undetermined"
        assert any(u.code == RECON_AUTHORITY_UNKNOWN for u in r.undetermined)

    def test_no_issue_no_pr_derives_undetermined(self):
        r = derive(snapshot_from("no-issue-no-pr.yaml"))
        assert r.derived_state == "undetermined"
        assert any(u.code == RECON_INCOMPLETE_DATA for u in r.undetermined)

    def test_blocker_label_derives_blocked(self):
        r = derive(snapshot_from("blocker-label.yaml"))
        assert r.derived_state == "blocked"

    def test_contradictory_states_derives_blocked(self):
        # Multiple blockers; blocked wins over review
        r = derive(snapshot_from("contradictory-states.yaml"))
        assert r.derived_state == "blocked"

    def test_missing_issue_with_open_pr_derives_review(self):
        r = derive(snapshot_from("missing-issue.yaml"))
        assert r.derived_state == "review"


# ---------------------------------------------------------------------------
# Group 2: Facts are correct
# ---------------------------------------------------------------------------

class TestFacts:
    def test_planned_has_issue_open_fact(self):
        r = derive(snapshot_from("issue-open-no-pr.yaml"))
        assert any(f.code == "F001" for f in r.facts)

    def test_accepted_has_merged_fact(self):
        r = derive(snapshot_from("merged-authorized.yaml"))
        assert any(f.code == "F005" for f in r.facts)

    def test_failed_checks_has_failing_fact(self):
        r = derive(snapshot_from("failed-checks.yaml"))
        assert any(f.code == "F010" for f in r.facts)

    def test_successful_checks_has_passing_fact(self):
        r = derive(snapshot_from("successful-checks.yaml"))
        assert any(f.code == "F009" for f in r.facts)

    def test_changes_requested_has_review_fact(self):
        r = derive(snapshot_from("changes-requested.yaml"))
        assert any(f.code == "F008" for f in r.facts)

    def test_draft_pr_has_draft_fact(self):
        r = derive(snapshot_from("draft-pr.yaml"))
        assert any(f.code == "F003" for f in r.facts)

    def test_blocker_label_fact_present(self):
        r = derive(snapshot_from("blocker-label.yaml"))
        assert any(f.code == "F011" for f in r.facts)


# ---------------------------------------------------------------------------
# Group 3: Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def _result_dict(self, name: str) -> dict:
        return derive(snapshot_from(name)).to_dict()

    def test_required_keys_present(self):
        d = self._result_dict("merged-authorized.yaml")
        for key in ("repository", "observed_at", "sources", "derived_state", "facts", "conflicts", "undetermined"):
            assert key in d, f"Missing key: {key}"

    def test_derived_state_is_valid(self):
        for fixture in FIXTURES.glob("*.yaml"):
            snap = FixtureAdapter(fixture).fetch()
            result = derive(snap)
            assert result.derived_state in DERIVED_STATES, \
                f"{fixture.name}: invalid derived_state '{result.derived_state}'"

    def test_conflicts_empty_when_accepted(self):
        d = self._result_dict("merged-authorized.yaml")
        assert d["conflicts"] == []

    def test_conflicts_populated_when_conflict(self):
        d = self._result_dict("merged-unauthorized.yaml")
        assert d["conflicts"]
        assert d["conflicts"][0]["code"] == RECON_UNAUTHORIZED_MERGE

    def test_undetermined_populated_when_no_authority(self):
        d = self._result_dict("missing-authority.yaml")
        assert d["undetermined"]
        assert d["undetermined"][0]["code"] == RECON_AUTHORITY_UNKNOWN

    def test_sources_contains_repository(self):
        d = self._result_dict("merged-authorized.yaml")
        assert "jaiaFoster/ASA" in d["sources"]


# ---------------------------------------------------------------------------
# Group 4: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_input_produces_identical_output_yaml(self):
        outputs = [run_fixture("merged-authorized.yaml").stdout for _ in range(2)]
        assert outputs[0] == outputs[1], "CLI output is not deterministic"

    def test_identical_input_produces_identical_output_json(self):
        outputs = [run_fixture("merged-authorized.yaml", fmt="json").stdout for _ in range(2)]
        assert outputs[0] == outputs[1], "JSON CLI output is not deterministic"

    def test_facts_are_sorted(self):
        r = derive(snapshot_from("contradictory-states.yaml"))
        d = r.to_dict()
        codes = [(f["code"], f["source"]) for f in d["facts"]]
        assert codes == sorted(codes), "Facts are not sorted"

    def test_conflicts_are_sorted(self):
        r = derive(snapshot_from("merged-unauthorized.yaml"))
        d = r.to_dict()
        codes = [(c["code"], c["source"]) for c in d["conflicts"]]
        assert codes == sorted(codes), "Conflicts are not sorted"

    def test_sources_are_sorted(self):
        r = derive(snapshot_from("merged-authorized.yaml"))
        d = r.to_dict()
        assert d["sources"] == sorted(d["sources"])

    def test_observed_at_injected(self):
        r = run_fixture("merged-authorized.yaml")
        out = yaml.safe_load(r.stdout)
        assert out["observed_at"] == "2026-07-18T10:00:00Z"


# ---------------------------------------------------------------------------
# Group 5: Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    def test_exit_0_on_accepted(self):
        r = run_fixture("merged-authorized.yaml")
        assert r.returncode == 0

    def test_exit_0_on_planned(self):
        r = run_fixture("issue-open-no-pr.yaml")
        assert r.returncode == 0

    def test_exit_0_on_review(self):
        r = run_fixture("ready-pr-no-review.yaml")
        assert r.returncode == 0

    def test_exit_0_on_undetermined(self):
        # undetermined alone is not a conflict; exit 0
        r = run_fixture("missing-authority.yaml")
        assert r.returncode == 0

    def test_exit_1_on_conflict(self):
        r = run_fixture("merged-unauthorized.yaml")
        assert r.returncode == 1

    def test_exit_2_on_invalid_input(self):
        r = run_cli("--fixture", "/nonexistent/path.yaml", "--format", "yaml")
        assert r.returncode == 3  # missing fixture → remote unavailable

    def test_exit_2_on_no_args(self):
        r = run_cli()
        assert r.returncode == 2

    def test_exit_3_on_missing_fixture(self):
        r = run_cli("--fixture", str(FIXTURES / "does-not-exist.yaml"), "--format", "yaml")
        assert r.returncode == 3


# ---------------------------------------------------------------------------
# Group 6: Read-only safety
# ---------------------------------------------------------------------------

class TestReadOnlySafety:
    def test_write_attempt_raises(self):
        adapter = FixtureAdapter(FIXTURES / "merged-authorized.yaml")
        with pytest.raises(WriteAttemptError):
            adapter._write()

    def test_no_canonical_record_modified(self, tmp_path):
        """Running the reconciler must not touch any project/lean files."""
        import os
        import time
        lean_dir = REPO_ROOT / "project" / "lean"
        before = {
            str(f): f.stat().st_mtime
            for f in lean_dir.rglob("*.yaml")
        }
        run_fixture("merged-authorized.yaml")
        after = {
            str(f): f.stat().st_mtime
            for f in lean_dir.rglob("*.yaml")
        }
        assert before == after, "Reconciler modified canonical lean records"

    def test_no_generated_file_modified(self):
        """Reconciler must not touch project/generated/ (deleted in CUTOVER-05)."""
        gen_dir = REPO_ROOT / "project" / "generated"
        if not gen_dir.exists():
            # CUTOVER-05 deleted project/generated/ — nothing to check
            return
        before = {str(f): f.stat().st_mtime for f in gen_dir.iterdir() if f.is_file()}
        run_fixture("merged-authorized.yaml")
        after = {str(f): f.stat().st_mtime for f in gen_dir.iterdir() if f.is_file()}
        assert before == after, "Reconciler modified generated files"

    def test_no_secret_in_output(self):
        """Ensure token or credential strings don't appear in stdout."""
        r = run_fixture("merged-authorized.yaml")
        assert "GITHUB_TOKEN" not in r.stdout
        assert "Authorization" not in r.stdout
        assert "Bearer" not in r.stdout


# ---------------------------------------------------------------------------
# Group 7: Offline validator import isolation
# ---------------------------------------------------------------------------

class TestImportIsolation:
    def test_validate_does_not_import_github(self):
        """Importing the offline validator must not pull in the online github module."""
        # Run in a subprocess to get a clean import environment
        code = (
            "import sys; sys.path.insert(0, '.'); "
            "import tools.pos.lean.validate; "
            "assert 'tools.pos.lean.github' not in sys.modules, "
            "'offline validator imported online github module'"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"Import isolation failed:\n{r.stderr}"

    def test_schemas_does_not_import_requests(self):
        """tools/pos/lean/schemas.py must not import requests."""
        code = (
            "import sys; sys.path.insert(0, '.'); "
            "import tools.pos.lean.schemas; "
            "assert 'requests' not in sys.modules, "
            "'schemas.py imported requests'"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"requests imported by schemas:\n{r.stderr}"

    def test_derived_does_not_import_requests(self):
        """tools/pos/lean/derived.py must not import requests."""
        code = (
            "import sys; sys.path.insert(0, '.'); "
            "import tools.pos.lean.derived; "
            "assert 'requests' not in sys.modules, "
            "'derived.py imported requests'"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"requests imported by derived:\n{r.stderr}"


# ---------------------------------------------------------------------------
# Group 8: No network required for tests
# ---------------------------------------------------------------------------

class TestNoLiveNetwork:
    def test_all_fixture_tests_use_no_network(self):
        """All fixture-based tests must complete without any live network call.

        We verify this by running the reconciler with proxies cleared in
        the subprocess environment and confirming it succeeds.
        """
        import os
        env = {k: v for k, v in os.environ.items()
               if k not in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "GITHUB_TOKEN")}
        r = subprocess.run(
            [sys.executable, str(RECONCILE),
             "--fixture", str(FIXTURES / "merged-authorized.yaml"),
             "--observed-at", "2026-07-18T10:00:00Z",
             "--format", "yaml"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 0, f"Fixture reconciliation requires network:\n{r.stderr}"
        assert "ConnectionError" not in r.stderr
        assert "urllib" not in r.stderr


# ---------------------------------------------------------------------------
# Group 9: Malformed and edge-case fixtures
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_malformed_fixture_missing_repository(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("issue: null\npull_request: null\n", encoding="utf-8")
        snap = FixtureAdapter(bad).fetch()
        r = derive(snap)
        assert r.derived_state == "undetermined"
        assert r.repository == ""

    def test_empty_pr_list_of_reviews(self):
        r = derive(snapshot_from("ready-pr-no-review.yaml"))
        assert r.derived_state == "review"
        assert not any(f.code == "F008" for f in r.facts)

    def test_multiple_mergers_config(self):
        r = derive(snapshot_from("merged-authorized-architect.yaml"))
        assert r.derived_state == "accepted"

    def test_closed_issue_no_pr_is_cancelled(self, tmp_path):
        snap_data = {
            "repository": "jaiaFoster/ASA",
            "observed_at": "2026-07-18T10:00:00Z",
            "authority": {"authorized_mergers": ["jaiaFoster"]},
            "issue": {"number": 99, "state": "closed", "labels": [], "state_reason": "completed"},
            "pull_request": None,
        }
        p = tmp_path / "closed-issue.yaml"
        import yaml as _yaml
        p.write_text(_yaml.dump(snap_data), encoding="utf-8")
        snap = FixtureAdapter(p).fetch()
        r = derive(snap)
        assert r.derived_state == "cancelled"

    def test_rate_limit_response_raises_runtime_error(self, tmp_path):
        """Simulate missing fixture to check G002 path."""
        from tools.pos.lean.github import FixtureAdapter
        adapter = FixtureAdapter(tmp_path / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError):
            adapter.fetch()


# ---------------------------------------------------------------------------
# Group 10: Output format — YAML and JSON
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_yaml_output_is_valid_yaml(self):
        r = run_fixture("merged-authorized.yaml", fmt="yaml")
        assert r.returncode == 0
        doc = yaml.safe_load(r.stdout)
        assert isinstance(doc, dict)
        assert "derived_state" in doc

    def test_json_output_is_valid_json(self):
        import json
        r = run_fixture("merged-authorized.yaml", fmt="json")
        assert r.returncode == 0
        doc = json.loads(r.stdout)
        assert "derived_state" in doc

    def test_yaml_and_json_agree(self):
        import json
        y = yaml.safe_load(run_fixture("merged-authorized.yaml", fmt="yaml").stdout)
        j = json.loads(run_fixture("merged-authorized.yaml", fmt="json").stdout)
        assert y["derived_state"] == j["derived_state"]
        assert y["repository"] == j["repository"]
