from pathlib import Path

from market_data.documentation import (
    PROVIDER_DOCUMENTATION,
    documentation_drift,
    generated_documents,
)

ROOT = Path(__file__).parents[2]


def test_all_provider_pages_and_capability_matrix_are_generated_without_drift() -> None:
    expected = {f"docs/providers/{item.provider_id}.md" for item in PROVIDER_DOCUMENTATION}
    expected.add("docs/providers/CAPABILITY_MATRIX.md")
    assert set(generated_documents()) == expected
    assert documentation_drift(ROOT) == ()


def test_generated_documentation_is_secret_free_and_actionable() -> None:
    content = "\n".join(generated_documents().values())
    lowered = content.lower()
    assert "test-token" not in content
    assert "test-key" not in content
    assert "authorization:" not in lowered
    assert "known limitations" in lowered
    assert "bounded validation" in lowered
    assert "asa_finnhub_api_key" in lowered


def test_finnhub_page_documents_candle_failure_diagnostics() -> None:
    page = generated_documents()["docs/providers/finnhub.md"]
    assert "resolution D" in page
    assert "UTC epoch" in page
    assert "no_data" in page
    assert "empty_payload" in page
    assert "entitlement" in page
    assert "30/second" in page
