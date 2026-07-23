from __future__ import annotations

from datetime import UTC, datetime, timedelta

from asa.api.agent_models import AgentApiError, TimestampedResource, agent_api_error


class TestTimestampedResource:
    def test_age_seconds_since_computes_elapsed_time(self) -> None:
        updated_at = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
        now = updated_at + timedelta(seconds=90)
        assert TimestampedResource.age_seconds_since(updated_at, now=now) == 90

    def test_age_seconds_since_never_goes_negative(self) -> None:
        updated_at = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
        now = updated_at - timedelta(seconds=5)
        assert TimestampedResource.age_seconds_since(updated_at, now=now) == 0

    def test_age_seconds_since_defaults_to_the_real_clock(self) -> None:
        updated_at = datetime.now(UTC) - timedelta(seconds=5)
        age = TimestampedResource.age_seconds_since(updated_at)
        assert 4 <= age <= 10


class TestAgentApiError:
    def test_agent_api_error_builds_a_deterministic_shaped_http_exception(self) -> None:
        exc = agent_api_error(404, "not_found", "no such resource")
        assert exc.status_code == 404
        assert exc.detail == {"error_code": "not_found", "message": "no such resource"}

    def test_agent_api_error_model_matches_the_http_exception_detail(self) -> None:
        model = AgentApiError(error_code="not_found", message="no such resource")
        exc = agent_api_error(404, "not_found", "no such resource")
        assert exc.detail == model.model_dump()
