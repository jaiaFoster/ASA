"""STONK-001 revision-pinned inventory contract tests."""

from __future__ import annotations

from pathlib import Path
import re

CATALOG = Path(__file__).parents[2] / "docs/migration/stonk-strategy-catalog.yaml"


def catalog_text() -> str:
    return CATALOG.read_text(encoding="utf-8")


def section(text: str, start: str, end: str) -> str:
    return text.split(f"{start}:\n", 1)[1].split(f"\n{end}:", 1)[0]


def test_inventory_is_revision_pinned_and_complete() -> None:
    text = catalog_text()
    assert "repository: https://github.com/jaiaFoster/Stonk" in text
    assert "revision: 5f3fec846f70e9739cf3f15695fd587f0604344c" in text
    production = section(text, "production_strategies", "non_production_strategy_artifacts")
    assert set(re.findall(r"^  - id: (\S+)$", production, re.MULTILINE)) == {
        "earnings_calendar",
        "forward_factor_calendar",
        "skew_momentum_vertical",
        "stock_momentum",
    }


def test_every_strategy_has_traceable_behavior_and_migration_shape() -> None:
    production = section(
        catalog_text(), "production_strategies", "non_production_strategy_artifacts"
    )
    assert production.count("execution_source: app/services/") == 4
    assert production.count("required_evidence:") == 4
    assert production.count("strategy_logic:") == 4
    assert production.count("primary_outputs:") == 4
    assert len(re.findall(r"manifest: \S+\.v1$", production, re.MULTILINE)) == 4


def test_test_clone_and_adjacent_capabilities_are_not_misclassified() -> None:
    artifacts = section(
        catalog_text(), "non_production_strategy_artifacts", "shared_component_candidates"
    )
    assert "id: stock_momentum_unified_test\n    classification: disabled_test_clone" in artifacts
    assert (
        "id: custom_strategy_builder\n    classification: authoring_and_validation_capability"
        in artifacts
    )


def test_shared_component_analysis_is_nonempty_and_unique() -> None:
    components = re.findall(
        r"^  - (\S+)$",
        catalog_text().split("shared_component_candidates:\n", 1)[1],
        re.MULTILINE,
    )
    assert len(components) >= 10
    assert len(components) == len(set(components))
