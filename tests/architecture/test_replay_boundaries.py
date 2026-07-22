from pathlib import Path


def test_replay_has_no_storage_network_clock_or_randomness() -> None:
    root = Path(__file__).parents[2]
    source = (root / "simulation" / "replay.py").read_text(encoding="utf-8").lower()
    for prohibited in (
        "requests", "sqlalchemy", "repository", "open(", "random", "uuid",
        "datetime.now", "datetime.utcnow", "socket", "providers",
    ):
        assert prohibited not in source


def test_replay_records_complete_semantic_inputs_and_outputs() -> None:
    root = Path(__file__).parents[2]
    source = (root / "domain" / "replay.py").read_text(encoding="utf-8")
    for field in (
        "execution_plan", "simulation_market_data", "expected_simulation_result",
        "expected_simulated_delta", "expected_next_snapshot", "expected_lifecycle",
        "input_digest", "output_digest",
    ):
        assert field in source
