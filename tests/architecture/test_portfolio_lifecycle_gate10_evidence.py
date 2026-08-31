from pathlib import Path


def test_gate_10_evidence_preserves_deployment_and_production_proof_gate() -> None:
    evidence = (
        Path(__file__).parents[2]
        / "docs/sprints/PORTFOLIO-LIFECYCLE-001-GATE-10-EVIDENCE.md"
    ).read_text()

    assert "remains open until Founder-authorized production verification succeeds" in evidence
    assert "Deployment authority is not implied" in evidence
    assert "No order submission" in evidence
