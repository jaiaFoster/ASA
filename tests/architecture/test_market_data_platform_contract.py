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


def test_arch_007a_keeps_capabilities_closed_and_uses_projections() -> None:
    text = CONTRACT.read_text()
    assert "This taxonomy is closed for v1" in text
    assert "typed field projections of `OPTION_CHAIN_V1`" in text
    assert "Provider features do not create capabilities" in text


def test_arch_007a_keeps_per_check_statuses_closed() -> None:
    text = CONTRACT.read_text()
    assert "The per-check status set is closed" in text
    assert "`SKIPPED` with `NOT_CONFIGURED` detail" in text
    assert "`FAIL` with `INCONCLUSIVE` detail" in text
    assert "`BUDGET_EXHAUSTED` detail" in text


def test_arch_007a_prohibits_statistical_resolution() -> None:
    text = CONTRACT.read_text()
    assert "Median, mean, weighted aggregation, voting, statistical fusion" in text
    assert "never manufactures a consensus value" in text
    assert "separate Founder-approved architecture amendment" in text
