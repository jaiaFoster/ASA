from pathlib import Path


def test_market_data_replay_cannot_import_acquisition_dependencies() -> None:
    source = (Path(__file__).parents[2] / "market_data" / "replay.py").read_text().lower()
    prohibited = (
        "providerfactory",
        "providerregistry",
        "marketdataprovider",
        "readonlyhttptransport",
        "load_market_data_config",
        "socket",
        "requests",
        "httpx",
        "urllib",
    )
    assert not tuple(item for item in prohibited if item in source)
