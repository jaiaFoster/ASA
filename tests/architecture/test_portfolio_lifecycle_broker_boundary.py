from pathlib import Path


def test_robinhood_identity_does_not_leak_into_generic_portfolio_owners() -> None:
    root = Path(__file__).parents[2] / "asa"
    inspected = (
        root / "application" / "ports" / "brokers.py",
        root / "application" / "portfolio_use_cases.py",
        root / "contracts" / "portfolio.py",
    )

    violations = [
        str(path.relative_to(root))
        for path in inspected
        if "robinhood" in path.read_text().lower()
    ]

    assert not violations, f"Robinhood identity leaked into generic portfolio owners: {violations}"
