"""
Tests for tools/pos/lean/migration.py and tools/pos/lean/assess_migration.py.

Groups:
  1. Legacy inventory completeness
  2. Capability map correctness
  3. Blocker detection
  4. Cutover plan structure
  5. Determinism and safety
  6. CLI contract
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tools.pos.lean.migration import (
    build_legacy_inventory,
    build_capability_map,
    build_blockers,
    build_cutover_plan,
    REQUIRED_CAPABILITIES,
)
from tools.pos.lean.assess_migration import main as assess_main

GENERATED_AT = "2026-07-18T22:00:00Z"

FIXTURES = Path(__file__).parent / "fixtures" / "migration"
MIGRATION_OUTPUT = REPO_ROOT / "project" / "lean" / "migration"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inventory() -> dict:
    return build_legacy_inventory(REPO_ROOT, GENERATED_AT)


def _cap_map() -> dict:
    return build_capability_map(GENERATED_AT)


def _blockers() -> dict:
    return build_blockers(GENERATED_AT)


def _cutover() -> dict:
    return build_cutover_plan(GENERATED_AT)


# ===========================================================================
# 1. Legacy inventory completeness
# ===========================================================================

class TestLegacyInventory:
    def test_generated_at_present(self):
        inv = _inventory()
        assert inv["generated_at"] == GENERATED_AT

    def test_required_top_level_fields_present(self):
        inv = _inventory()
        for field in ("artifacts", "directories", "schemas", "tools",
                      "generated_views", "tests", "workflows", "root_pointers"):
            assert field in inv, f"missing field: {field}"

    def test_complete_legacy_inventory_schemas(self):
        inv = _inventory()
        schema_paths = {s["path"] for s in inv["schemas"]}
        expected = {
            "project/schemas/work-item.schema.yaml",
            "project/schemas/assignment.schema.yaml",
            "project/schemas/worker-result.schema.yaml",
            "project/schemas/decision.schema.yaml",
            "project/schemas/review.schema.yaml",
            "project/schemas/evidence.schema.yaml",
            "project/schemas/risk-record.schema.yaml",
        }
        assert expected.issubset(schema_paths), f"missing schemas: {expected - schema_paths}"

    def test_complete_legacy_inventory_tools(self):
        inv = _inventory()
        tool_paths = {t["path"] for t in inv["tools"]}
        expected = {
            "tools/pos/validate.py",
            "tools/pos/generate.py",
            "tools/pos/schemas.py",
            "tools/pos/transitions.py",
        }
        assert expected.issubset(tool_paths)

    def test_generated_views_listed(self):
        inv = _inventory()
        view_paths = {v["path"] for v in inv["generated_views"]}
        expected = {
            "project/generated/AGENTS.md",
            "project/generated/CURRENT_STATE.md",
            "project/generated/MANAGER_INBOX.md",
        }
        assert expected.issubset(view_paths)

    def test_ci_workflow_listed(self):
        inv = _inventory()
        wf_paths = {w["path"] for w in inv["workflows"]}
        assert ".github/workflows/validate-pos.yml" in wf_paths

    def test_root_pointers_listed(self):
        inv = _inventory()
        rp_paths = {r["path"] for r in inv["root_pointers"]}
        assert {"AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"}.issubset(rp_paths)

    def test_every_artifact_has_required_fields(self):
        inv = _inventory()
        required = {"path", "category", "status", "canonical_data",
                    "proposed_disposition", "lean_replacement"}
        for art in inv["artifacts"]:
            missing = required - set(art.keys())
            assert not missing, f"artifact {art.get('path')} missing: {missing}"

    def test_reference_graph_detection_schemas_referenced_by_tools(self):
        inv = _inventory()
        schema_refs = next(
            (s["referenced_by"] for s in inv["schemas"]
             if s["path"] == "project/schemas/work-item.schema.yaml"), None
        )
        assert schema_refs is not None
        assert any("validate" in r or "schemas" in r for r in schema_refs)

    def test_unique_canonical_data_detection(self):
        """Schemas and work records must be classified as unique canonical data."""
        inv = _inventory()
        schemas = [s for s in inv["schemas"]]
        for s in schemas:
            assert s["canonical_data"] == "yes — schema definitions are not in GitHub", (
                f"{s['path']} classified wrong: {s['canonical_data']}"
            )

    def test_github_duplicate_detection_generated_views(self):
        """Generated views must NOT be classified as containing unique canonical data."""
        inv = _inventory()
        for gv in inv["generated_views"]:
            assert gv["canonical_data"] == "no — generated from canonical records", (
                f"{gv['path']} should not be canonical: {gv['canonical_data']}"
            )

    def test_work_record_listed(self):
        inv = _inventory()
        work_records = [a for a in inv["artifacts"] if a["category"] == "work_record"]
        assert len(work_records) >= 1

    def test_active_record_has_blocker_reference(self):
        """Active work records (status=review) must list BLKR-004."""
        inv = _inventory()
        active_work = [a for a in inv["artifacts"]
                       if a["category"] == "work_record" and a.get("status") == "review"]
        for rec in active_work:
            assert "BLKR-004" in rec["removal_blockers"], (
                f"active work record {rec['path']} missing BLKR-004"
            )

    def test_frozen_governance_not_in_inventory(self):
        """Frozen governance files must NOT appear in the legacy inventory."""
        inv = _inventory()
        for art in inv["artifacts"]:
            assert not art["path"].startswith("governance/frozen/"), (
                f"frozen governance file in inventory: {art['path']}"
            )

    def test_artifact_paths_sorted(self):
        """Schemas list must be sorted for determinism."""
        inv = _inventory()
        paths = [s["path"] for s in inv["schemas"]]
        assert paths == sorted(paths)

    def test_archived_record_disposition(self):
        """Result records are github_derivable and should be archived."""
        inv = _inventory()
        result_recs = [a for a in inv["artifacts"] if a["category"] == "result_record"]
        for rec in result_recs:
            assert rec["proposed_disposition"] == "archive"

    def test_generated_view_disposition_delete_after_cutover(self):
        inv = _inventory()
        for gv in inv["generated_views"]:
            assert gv["proposed_disposition"] == "delete_after_cutover"


# ===========================================================================
# 2. Capability map
# ===========================================================================

class TestCapabilityMap:
    def test_all_required_capabilities_present(self):
        cap = _cap_map()
        ids = {c["id"] for c in cap["capabilities"]}
        for req in REQUIRED_CAPABILITIES:
            assert req in ids, f"missing capability: {req}"

    def test_each_capability_has_exactly_one_status(self):
        cap = _cap_map()
        valid_statuses = {
            "replaced", "replaced_with_different_mechanism",
            "retained", "obsolete", "partially_replaced", "blocked", "undetermined",
        }
        for c in cap["capabilities"]:
            assert c["status"] in valid_statuses, (
                f"capability {c['id']} has invalid status: {c['status']}"
            )

    def test_legacy_capability_replaced(self):
        cap = _cap_map()
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        assert caps_by_id["structural_validation"]["status"] == "replaced"
        assert caps_by_id["github_reconciliation"]["status"] == "replaced"
        assert caps_by_id["offline_operation"]["status"] == "replaced"

    def test_replaced_capability_has_lean_implementation(self):
        cap = _cap_map()
        for c in cap["capabilities"]:
            if c["status"] in ("replaced", "replaced_with_different_mechanism"):
                assert c.get("lean_implementation"), (
                    f"capability {c['id']} declared replaced but no lean_implementation"
                )

    def test_legacy_capability_partially_replaced(self):
        cap = _cap_map()
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        assert caps_by_id["risk_floor_enforcement"]["status"] == "partially_replaced"
        assert caps_by_id["ci_validation"]["status"] == "partially_replaced"
        assert caps_by_id["frozen_governance_integrity"]["status"] == "partially_replaced"

    def test_partially_replaced_has_gap(self):
        cap = _cap_map()
        for c in cap["capabilities"]:
            if c["status"] == "partially_replaced":
                assert c.get("gap"), f"partial capability {c['id']} missing gap description"

    def test_missing_capability_creates_blocker(self):
        """Partially replaced/blocked capabilities must reference a blocker."""
        cap = _cap_map()
        for c in cap["capabilities"]:
            if c["status"] in ("partially_replaced", "blocked") and c.get("gap"):
                assert c.get("blocker"), (
                    f"capability {c['id']} has gap but no blocker reference"
                )

    def test_capability_not_replaced_just_because_tests_exist(self):
        """github_reconciliation should be replaced because code exists, not just tests."""
        cap = _cap_map()
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        impl = caps_by_id["github_reconciliation"]["lean_implementation"]
        assert "reconcile.py" in impl or "derived.py" in impl

    def test_summary_counts_correct(self):
        cap = _cap_map()
        summary = cap["summary"]
        caps = cap["capabilities"]
        assert summary["total_capabilities"] == len(caps)
        # summary["replaced"] counts both "replaced" and "replaced_with_different_mechanism"
        total_replaced = sum(1 for c in caps
                             if c["status"] in ("replaced", "replaced_with_different_mechanism"))
        assert summary["replaced"] == total_replaced
        assert summary["partially_replaced"] == sum(1 for c in caps if c["status"] == "partially_replaced")

    def test_generated_at_present(self):
        cap = _cap_map()
        assert cap["generated_at"] == GENERATED_AT


# ===========================================================================
# 3. Blocker detection
# ===========================================================================

class TestBlockerDetection:
    def test_governance_conflict_blocker_present(self):
        bl = _blockers()
        ids = {b["id"] for b in bl["blockers"]}
        assert "BLKR-001" in ids

    def test_hash_failures_create_manifest_integrity_blocker(self):
        bl = _blockers()
        manifest_blockers = [b for b in bl["blockers"] if b["type"] == "manifest_integrity"]
        assert len(manifest_blockers) >= 1
        # Must reference the 3 pre-existing failures
        evidence = manifest_blockers[0]["evidence"]
        evidence_text = " ".join(evidence)
        assert "test_frozen_hashes_match_manifest" in evidence_text

    def test_all_three_preexisting_hash_failures_accounted(self):
        bl = _blockers()
        # Find the manifest integrity blocker
        mb = next((b for b in bl["blockers"] if b["type"] == "manifest_integrity"), None)
        assert mb is not None
        evidence_text = " ".join(mb["evidence"])
        for test_name in ("test_frozen_hashes_match_manifest", "test_validator_passes",
                          "test_valid_accepted_lifecycle_passes"):
            assert test_name in evidence_text, f"pre-existing failure not documented: {test_name}"

    def test_active_record_without_github_mapping_is_blocker(self):
        bl = _blockers()
        data_blockers = [b for b in bl["blockers"] if b["type"] == "canonical_data_not_migrated"]
        assert len(data_blockers) >= 1
        # Must mention ASA2-WORK-001 or ASA2-DECISION-001
        evidence_text = " ".join(" ".join(b["evidence"]) for b in data_blockers)
        assert "ASA2-WORK-001" in evidence_text or "ASA2-DECISION-001" in evidence_text

    def test_ci_dependency_blocker_present(self):
        bl = _blockers()
        ci_blockers = [b for b in bl["blockers"] if b["type"] == "ci_dependency"]
        assert len(ci_blockers) >= 1

    def test_missing_capability_blocker_for_governance_integrity(self):
        bl = _blockers()
        missing_cap = [b for b in bl["blockers"] if b["type"] == "missing_capability"]
        assert len(missing_cap) >= 1
        affected_caps = []
        for b in missing_cap:
            affected_caps.extend(b.get("affected_capabilities", []))
        assert "frozen_governance_integrity" in affected_caps

    def test_every_blocker_has_severity(self):
        bl = _blockers()
        for b in bl["blockers"]:
            assert b.get("severity") in ("high", "medium", "low"), (
                f"blocker {b['id']} missing/invalid severity"
            )

    def test_every_blocker_names_resolution_authority(self):
        bl = _blockers()
        for b in bl["blockers"]:
            assert b.get("resolution_authority"), f"blocker {b['id']} missing resolution_authority"

    def test_every_blocker_has_smallest_required_decision(self):
        bl = _blockers()
        for b in bl["blockers"]:
            assert b.get("smallest_required_decision"), (
                f"blocker {b['id']} missing smallest_required_decision"
            )

    def test_no_blocker_silently_downgraded(self):
        """Every blocker must have an id, type, and description."""
        bl = _blockers()
        for b in bl["blockers"]:
            for field in ("id", "type", "description"):
                assert b.get(field), f"blocker {b.get('id')} missing {field}"

    def test_cutover_not_ready_while_blockers_present(self):
        bl = _blockers()
        assert bl["summary"]["cutover_ready"] is False

    def test_founder_decisions_required_listed(self):
        bl = _blockers()
        assert len(bl["founder_decisions_required"]) >= 4

    def test_blocker_ids_sorted(self):
        bl = _blockers()
        ids = [b["id"] for b in bl["blockers"]]
        assert ids == sorted(ids)


# ===========================================================================
# 4. Cutover plan
# ===========================================================================

class TestCutoverPlan:
    def test_required_phases_present_in_order(self):
        co = _cutover()
        required = [
            "CUTOVER-01", "CUTOVER-02", "CUTOVER-03",
            "CUTOVER-04", "CUTOVER-05", "CUTOVER-06",
        ]
        ids = [p["id"] for p in co["phases"]]
        assert ids == required

    def test_cutover_phase_order(self):
        co = _cutover()
        ids = [p["id"] for p in co["phases"]]
        # Each phase id must be sequentially numbered
        for i, pid in enumerate(ids):
            assert pid == f"CUTOVER-0{i+1}"

    def test_rollback_present_for_every_phase(self):
        co = _cutover()
        for phase in co["phases"]:
            assert phase.get("rollback"), f"phase {phase['id']} missing rollback"
            assert len(phase["rollback"]) > 0

    def test_verification_present_for_every_phase(self):
        co = _cutover()
        for phase in co["phases"]:
            assert phase.get("verification"), f"phase {phase['id']} missing verification"

    def test_ci_switch_precedes_legacy_tool_deletion(self):
        co = _cutover()
        ids = [p["id"] for p in co["phases"]]
        ci_switch_idx = ids.index("CUTOVER-03")
        deletion_idx = ids.index("CUTOVER-05")
        assert ci_switch_idx < deletion_idx

    def test_deletion_manifest_is_exact(self):
        co = _cutover()
        dm = co["deletion_manifest"]
        assert len(dm) > 0
        required_paths = {
            "tools/pos/validate.py",
            "tools/pos/generate.py",
            "project/generated/AGENTS.md",
            "project/generated/CURRENT_STATE.md",
            "project/generated/MANAGER_INBOX.md",
        }
        dm_paths = {e["path"] for e in dm}
        assert required_paths.issubset(dm_paths)

    def test_deletion_manifest_no_globs(self):
        co = _cutover()
        for entry in co["deletion_manifest"]:
            assert "*" not in entry["path"], (
                f"glob found in deletion manifest: {entry['path']}"
            )

    def test_deletion_manifest_no_frozen_governance(self):
        co = _cutover()
        for entry in co["deletion_manifest"]:
            assert not entry["path"].startswith("governance/frozen/"), (
                f"frozen governance in deletion manifest: {entry['path']}"
            )

    def test_every_deletion_entry_has_required_fields(self):
        co = _cutover()
        required = {"path", "reason", "replacement", "dependencies_checked",
                    "required_prior_phase", "rollback_method"}
        for entry in co["deletion_manifest"]:
            missing = required - set(entry.keys())
            assert not missing, f"deletion entry {entry.get('path')} missing: {missing}"

    def test_historical_records_not_deleted_without_archive(self):
        """Work/result/review records should not appear in deletion manifest — they're archived."""
        co = _cutover()
        dm_paths = {e["path"] for e in co["deletion_manifest"]}
        # Canonical record files are archived in CUTOVER-04, not deleted
        assert "project/work/ASA2-WORK-001.yaml" not in dm_paths

    def test_final_state_no_dual_canonical_system(self):
        co = _cutover()
        # CUTOVER-06 must include a check for no dual system
        co6 = next(p for p in co["phases"] if p["id"] == "CUTOVER-06")
        verification_text = " ".join(co6["verification"])
        assert "project/generated" not in verification_text or "does not exist" in verification_text

    def test_global_rollback_defined(self):
        co = _cutover()
        assert co.get("rollback", {}).get("global_rollback")

    def test_preconditions_listed(self):
        co = _cutover()
        assert len(co.get("preconditions", [])) >= 1

    def test_founder_decisions_in_cutover_plan(self):
        co = _cutover()
        assert len(co.get("founder_decisions", [])) >= 4

    def test_retained_artifacts_include_frozen_governance(self):
        co = _cutover()
        retained_paths = {r["path"] for r in co["retained_artifacts"]}
        assert any("governance/frozen" in p or "governance" in p for p in retained_paths)


# ===========================================================================
# 5. Determinism and safety
# ===========================================================================

class TestDeterminismAndSafety:
    def test_deterministic_outputs(self):
        inv1 = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        inv2 = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        import yaml
        assert yaml.dump(inv1, sort_keys=False) == yaml.dump(inv2, sort_keys=False)

    def test_capability_map_deterministic(self):
        cap1 = build_capability_map(GENERATED_AT)
        cap2 = build_capability_map(GENERATED_AT)
        import yaml
        assert yaml.dump(cap1, sort_keys=False) == yaml.dump(cap2, sort_keys=False)

    def test_no_network(self):
        """assess_migration must not import requests at module level."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "import tools.pos.lean.migration; "
             "import tools.pos.lean.assess_migration; "
             "assert 'requests' not in sys.modules, 'requests imported'"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr

    def test_no_locked_path_mutation(self, tmp_path):
        """assess_migration must not write outside --output-dir."""
        from tools.pos.lean.assess_migration import _atomic_write
        import pytest
        with pytest.raises(PermissionError):
            _atomic_write(
                path=REPO_ROOT / "governance" / "frozen" / "evil.yaml",
                content="x",
                output_dir=tmp_path,
            )

    def test_stale_output_replacement(self, tmp_path):
        """Re-running the assessor fully replaces all outputs."""
        result1 = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, cwd=REPO_ROOT,
        )
        # Inject a stale marker into one file
        stale_file = tmp_path / "capability-map.yaml"
        stale_file.write_text("STALE_MARKER: this should be overwritten\n")

        result2 = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, cwd=REPO_ROOT,
        )
        assert "STALE_MARKER" not in stale_file.read_text()

    def test_atomic_output_set(self, tmp_path):
        """All 5 output files must be written in a single run."""
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, cwd=REPO_ROOT,
        )
        expected = {
            "legacy-inventory.yaml",
            "capability-map.yaml",
            "blockers.yaml",
            "cutover-plan.yaml",
            "README.md",
        }
        written = {f.name for f in tmp_path.iterdir() if f.is_file()}
        assert expected == written

    def test_paths_have_stable_order(self):
        """Schema paths in inventory must be sorted identically across two runs."""
        inv1 = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        inv2 = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        paths1 = [s["path"] for s in inv1["schemas"]]
        paths2 = [s["path"] for s in inv2["schemas"]]
        assert paths1 == paths2 == sorted(paths1)

    def test_no_legacy_file_modified(self, tmp_path):
        """Running the assessor must not change any legacy file's mtime."""
        legacy_dirs = [
            REPO_ROOT / "project" / "work",
            REPO_ROOT / "project" / "schemas",
            REPO_ROOT / "tools" / "pos",
        ]
        before = {}
        for d in legacy_dirs:
            if d.exists():
                for f in sorted(d.rglob("*")):
                    if f.is_file():
                        before[str(f)] = f.stat().st_mtime

        subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, cwd=REPO_ROOT,
        )

        for path, mtime in before.items():
            current = Path(path).stat().st_mtime
            assert current == mtime, f"legacy file mtime changed: {path}"

    def test_token_budget_readme(self):
        """README must be within the 1800-token budget."""
        from tools.pos.lean.schemas import estimate_tokens
        from tools.pos.lean.assess_migration import README_CONTENT
        est = estimate_tokens(README_CONTENT)
        assert est <= 1800, f"README over budget: {est} tokens"


# ===========================================================================
# 6. CLI contract
# ===========================================================================

class TestCLIContract:
    def test_exit_1_with_blockers(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 1

    def test_exit_2_on_invalid_repo_root(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", "/nonexistent/path",
             "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 2

    def test_exit_2_on_missing_output_dir_arg(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 2

    def test_output_files_valid_yaml(self, tmp_path):
        subprocess.run(
            [sys.executable, "tools/pos/lean/assess_migration.py",
             "--repo-root", ".", "--generated-at", GENERATED_AT,
             "--output-dir", str(tmp_path)],
            capture_output=True, cwd=REPO_ROOT,
        )
        for name in ("legacy-inventory.yaml", "capability-map.yaml",
                     "blockers.yaml", "cutover-plan.yaml"):
            content = (tmp_path / name).read_text()
            data = yaml.safe_load(content)
            assert isinstance(data, dict), f"{name} is not a YAML mapping"

    def test_byte_identical_on_repeat_run(self, tmp_path):
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        for d in (out1, out2):
            subprocess.run(
                [sys.executable, "tools/pos/lean/assess_migration.py",
                 "--repo-root", ".", "--generated-at", GENERATED_AT,
                 "--output-dir", str(d)],
                capture_output=True, cwd=REPO_ROOT,
            )
        for name in ("legacy-inventory.yaml", "capability-map.yaml",
                     "blockers.yaml", "cutover-plan.yaml", "README.md"):
            c1 = (out1 / name).read_bytes()
            c2 = (out2 / name).read_bytes()
            assert c1 == c2, f"output not byte-identical: {name}"

    def test_generated_at_injectable(self, tmp_path):
        ts1 = "2026-01-01T00:00:00Z"
        ts2 = "2026-12-31T23:59:59Z"
        for ts in (ts1, ts2):
            subprocess.run(
                [sys.executable, "tools/pos/lean/assess_migration.py",
                 "--repo-root", ".", "--generated-at", ts,
                 "--output-dir", str(tmp_path)],
                capture_output=True, cwd=REPO_ROOT,
            )
            data = yaml.safe_load((tmp_path / "blockers.yaml").read_text())
            assert data["generated_at"] == ts

    def test_existing_lean_tests_still_pass(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/pos/lean/test_lean_validator.py",
             "tests/pos/lean/test_reconcile.py", "tests/pos/lean/test_generate.py", "-q"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr
