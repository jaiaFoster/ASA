import json
import logging
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
