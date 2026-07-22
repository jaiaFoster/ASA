from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "architecture" / "ASA-ARCH-007-Market-Data-Platform.md"
SPRINT = ROOT / "docs" / "sprints" / "SPRINT-005A.yaml"


def test_market_data_contract_covers_every_authorized_work_package() -> None:
    text = CONTRACT.read_text()
    for number in range(1, 15):
        assert f"ARCH-MD-{number:03d}" in text


def test_market_data_contract_freezes_required_boundaries() -> None:
    text = CONTRACT.read_text()
    required = (
        "Provider-specific values never\nescape the adapter",
        "Strategies consume Canonical Facts and typed snapshot content",
        "Replay accepts only a sealed `MarketSnapshot`",
        "Providers and adapters never call `getenv`",
        "Registration occurs only during composition",
        "No runtime, provider implementation, persistence schema, live request",
    )
    for phrase in required:
        assert phrase in text


def test_sprint_charter_requires_founder_merge_and_forbids_runtime() -> None:
    text = SPRINT.read_text()
    assert "founder_required: true" in text
    assert "self_merge: false" in text
    assert "runtime_changes" in text
    assert "live_api_calls" in text
    assert "FOUNDER_REVIEW_REQUIRED" in text
