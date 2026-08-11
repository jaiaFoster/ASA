import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from asa.application.portfolio_use_cases import RunPortfolioIntelligence
from asa.application.ports.runs import RunPublicationRepository
from asa.contracts.runs import RunStepName
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from asa.logging import JsonFormatter, request_id_context


def test_structured_market_log_contains_required_correlation_fields() -> None:
    record = logging.LogRecord(
        name="asa.market",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="quote_observation_saved",
        args=(),
        exc_info=None,
    )
    record.provider_request_id = "fake-provider-request"
    record.symbol = "AAPL"
    record.provider = "deterministic_fake"
    record.run_id = "run-123"
    record.run_step = "acquire_portfolio"
    record.account_id = "taxable-001"
    token = request_id_context.set("http-request")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["request_id"] == "http-request"
    assert payload["provider_request_id"] == "fake-provider-request"
    assert payload["symbol"] == "AAPL"
    assert payload["provider"] == "deterministic_fake"
    assert payload["run_id"] == "run-123"
    assert payload["run_step"] == "acquire_portfolio"
    assert payload["account_id"] == "taxable-001"


def test_shadow_parity_diagnostic_fields_survive_the_allowlist() -> None:
    """SPRINT-014 S14-PR-05A (Architect checkpoint: sixteenth review, "log/
    record shadow diagnostics internally. At minimum retain status,
    mismatched fields, UNKNOWN code+demand IDs, and shadow snapshot ID/
    digest without provider payloads") -- both production roots' own
    shadow_parity_diagnostic log call sites are silently filtered through
    this exact allowlist; a field missing here means it is silently
    dropped from every real, production JSON log line, not just this
    test's own record.
    """
    record = logging.LogRecord(
        name="asa.api.screening_routes",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="shadow_parity_diagnostic",
        args=(),
        exc_info=None,
    )
    record.signal_id = "earnings_calendar"
    record.symbol = "AAPL"
    record.shadow_status = "mismatch"
    record.shadow_mismatched_fields = ("verdict",)
    record.shadow_unknown_code = "synthetic_gap"
    record.shadow_unknown_demand_ids = ("demand-a",)
    record.shadow_snapshot_id = "snapshot-1"
    record.shadow_snapshot_digest = "digest-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["shadow_status"] == "mismatch"
    assert payload["shadow_mismatched_fields"] == ["verdict"]
    assert payload["shadow_unknown_code"] == "synthetic_gap"
    assert payload["shadow_unknown_demand_ids"] == ["demand-a"]
    assert payload["shadow_snapshot_id"] == "snapshot-1"
    assert payload["shadow_snapshot_digest"] == "digest-1"


def _record_with_exc_info(exc: BaseException, msg: str = "operation failed") -> logging.LogRecord:
    try:
        raise exc
    except type(exc):
        record = logging.LogRecord(
            name="asa.test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=sys.exc_info(),
        )
    return record


class TestSanitizedExceptionDetail:
    """SPRINT-013 S13-11 (issue #242): exc_info=True previously produced no
    exception detail at all in the emitted JSON -- JsonFormatter never
    read record.exc_info. These tests exercise the fix directly against
    the formatter, the shared logging boundary, not a specific call site.
    """

    def test_exc_info_produces_exception_type_and_useful_safe_detail(self) -> None:
        record = _record_with_exc_info(ValueError("no put contracts at expiration 2026-08-21"))
        payload = json.loads(JsonFormatter().format(record))
        assert payload["exception_type"] == "ValueError"
        assert "no put contracts at expiration" in payload["exception_message"]
        assert payload["stack_location"]
        assert payload["stack_location"][0]["file"] == "test_logging.py"
        assert isinstance(payload["stack_location"][0]["line"], int)

    def test_traceback_information_survives_json_formatting(self) -> None:
        record = _record_with_exc_info(RuntimeError("boom"))
        formatted = JsonFormatter().format(record)
        # One valid JSON value, not multiple lines -- json.loads would
        # raise on anything but a single well-formed document.
        payload = json.loads(formatted)
        assert "\n" not in formatted
        assert payload["exception_type"] == "RuntimeError"
        for frame in payload["stack_location"]:
            assert set(frame) == {"file", "line", "function"}

    def test_secrets_in_the_exception_message_are_redacted(self) -> None:
        record = _record_with_exc_info(
            ValueError(
                "request to https://api.example.com/v1/quote?symbol=AAPL&token=sk-live-abc123 "
                "failed with header Authorization: Bearer sk-live-verysecrettoken"
            )
        )
        payload = json.loads(JsonFormatter().format(record))
        assert "sk-live-abc123" not in payload["exception_message"]
        assert "sk-live-verysecrettoken" not in payload["exception_message"]
        assert "[REDACTED]" in payload["exception_message"]

    def test_provider_shaped_payload_fragments_never_escape_via_extra(self) -> None:
        record = _record_with_exc_info(ValueError("boom"))
        record.raw_response = {"api_key": "super-secret", "quotes": [{"bid": 1}] * 500}
        record.headers = {"Authorization": "Bearer super-secret-header-token"}
        payload = json.loads(JsonFormatter().format(record))
        assert "raw_response" not in payload
        assert "headers" not in payload
        assert "super-secret" not in json.dumps(payload)

    def test_nested_exceptions_remain_bounded(self) -> None:
        try:
            try:
                try:
                    try:
                        raise ValueError("level 0")
                    except ValueError as inner:
                        raise TypeError("level 1") from inner
                except TypeError as inner:
                    raise KeyError("level 2") from inner
            except KeyError as inner:
                raise RuntimeError("level 3") from inner
        except RuntimeError as exc:
            record = logging.LogRecord(
                name="asa.test",
                level=logging.WARNING,
                pathname=__file__,
                lineno=1,
                msg="deeply nested failure",
                args=(),
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        payload = json.loads(JsonFormatter().format(record))
        assert payload["exception_type"] == "RuntimeError"
        assert len(payload["caused_by"]) <= 3

    def test_ordinary_non_exception_logs_are_unchanged(self) -> None:
        record = logging.LogRecord(
            name="asa.market",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="quote_observation_saved",
            args=(),
            exc_info=None,
        )
        record.symbol = "AAPL"
        payload = json.loads(JsonFormatter().format(record))
        assert payload["event"] == "quote_observation_saved"
        assert payload["symbol"] == "AAPL"
        assert "exception_type" not in payload
        assert "stack_location" not in payload

    def test_output_is_one_railway_compatible_json_line(self) -> None:
        record = _record_with_exc_info(ValueError("multi\nline\nmessage"))
        formatted = JsonFormatter().format(record)
        assert "\n" not in formatted
        assert json.loads(formatted)["exception_message"] == "multi\nline\nmessage"


def test_run_step_log_uses_provider_supplied_by_port(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    provider.name = "provider_selected_at_composition"
    repository = Mock(spec=RunPublicationRepository)
    runner = RunPortfolioIntelligence(provider, repository)

    with caplog.at_level(logging.INFO, logger="asa.portfolio_run"):
        runner._run_step(
            uuid4(),
            RunStepName.NORMALIZE_PORTFOLIO,
            provider.name,
            lambda: None,
        )

    assert caplog.records[-1].provider == "provider_selected_at_composition"
    application_source = (
        Path(__file__).parents[2] / "asa" / "application" / "portfolio_use_cases.py"
    ).read_text()
    assert "deterministic_fake_broker" not in application_source
