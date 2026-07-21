"""GOV-AMD-014 constitutional analytical-execution boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_constitution_defines_analytical_execution_without_broker_mutation() -> None:
    constitution = (ROOT / "architecture" / "CONSTITUTION.md").read_text(encoding="utf-8")
    required = (
        "ASA Core SHALL NOT submit, modify, cancel, or otherwise mutate brokerage state.",
        "ASA Core SHALL produce immutable Execution Plans",
        "Execution Plans are analytical artifacts and SHALL NOT have operational side effects.",
        "separately governed subsystem requiring constitutional amendment",
        "explicit Founder authorization",
    )
    assert all(text in constitution for text in required)
    assert "ASA is a read-only platform" not in constitution
    assert "does not execute trades, place orders" not in constitution


def test_amendment_preserves_live_broker_prohibitions_and_r5_lifecycle() -> None:
    amendment = (ROOT / "governance" / "amendments" / "GOV-AMD-014.md").read_text(
        encoding="utf-8"
    )
    assert "R5 — Constitutional" in amendment
    assert "Independent, Structural, and Constitutional Reviews" in amendment
    assert "Founder merges the amendment PR" in amendment
    assert "### Independent Review" in amendment
    assert "### Structural Review" in amendment
    assert "### Constitutional Review" in amendment
    for prohibited in (
        "submitting orders to a broker",
        "cancelling orders at a broker",
        "modifying orders at a broker",
        "authenticating with a broker",
        "placing live trades",
    ):
        assert prohibited in amendment


def test_existing_execution_contract_remains_inert() -> None:
    execution = (ROOT / "domain" / "execution.py").read_text(encoding="utf-8")
    adr = (ROOT / "architecture" / "ADR-009-execution-semantics.md").read_text(
        encoding="utf-8"
    )
    assert "not an API request" in execution
    assert "no side effect" in execution
    assert "BrokerRequest" in adr
    assert "analytical values" in adr
    normalized_adr = adr.lower()
    assert "broker adapter" in normalized_adr
    assert "sdk call" in normalized_adr
    assert "authentication flow" in normalized_adr
