from pathlib import Path


def test_provider_diagnostics_runbook_is_complete_and_secret_safe() -> None:
    path = Path(__file__).parents[2] / "docs/deployment/market-data-provider-diagnostics.md"
    content = path.read_text(encoding="utf-8")
    required = (
        "Preflight",
        "request plan",
        "Finnhub daily-candle diagnosis",
        "authentication_failed",
        "entitlement_missing",
        "empty_payload",
        "schema_mismatch",
        "rate_limited",
        "Safe retry",
        "Escalation template",
        "recommended_Founder_action",
        "evidence_artifact_paths",
    )
    assert all(item in content for item in required)
    assert "Never paste credentials" in content
    assert "12 requests per provider run" in content
    assert "HTTP 200 alone is never success" in content
