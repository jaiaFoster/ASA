import json
import logging

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
