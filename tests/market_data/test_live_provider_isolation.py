import pytest


@pytest.mark.live_provider
def test_live_provider_collection_is_disabled_by_default() -> None:
    """Sentinel: normal CI must skip this entire opt-in class of tests."""

    pytest.fail("live provider tests require ASA_LIVE_PROVIDER_VALIDATION=1")
