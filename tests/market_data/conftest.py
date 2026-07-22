from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get("ASA_LIVE_PROVIDER_VALIDATION") == "1":
        return
    skip = pytest.mark.skip(reason="live provider validation is opt-in and disabled by default")
    for item in items:
        if "live_provider" in item.keywords:
            item.add_marker(skip)
