from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from domain import MarketCapability, ProviderErrorKind
from market_data.providers import (
    MarketDataProvider,
    NormalizedProviderError,
    ProviderErrorCode,
    ValidationCheckStatus,
    normalized_provider_error,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)

EXPECTED_POLICY = {
    ProviderErrorCode.CONFIGURATION_ERROR: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.AUTHENTICATION_FAILED: (ProviderErrorKind.AUTHENTICATION, False),
    ProviderErrorCode.AUTHORIZATION_FAILED: (ProviderErrorKind.AUTHORIZATION, False),
    ProviderErrorCode.ENTITLEMENT_MISSING: (ProviderErrorKind.AUTHORIZATION, False),
    ProviderErrorCode.INVALID_REQUEST: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.UNSUPPORTED_CAPABILITY: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.UNSUPPORTED_SYMBOL: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.NO_DATA: (ProviderErrorKind.UNAVAILABLE, False),
    ProviderErrorCode.EMPTY_PAYLOAD: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.SCHEMA_MISMATCH: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.RATE_LIMITED: (ProviderErrorKind.RATE_LIMIT, True),
    ProviderErrorCode.QUOTA_EXHAUSTED: (ProviderErrorKind.RATE_LIMIT, False),
    ProviderErrorCode.TIMEOUT: (ProviderErrorKind.TIMEOUT, True),
    ProviderErrorCode.PROVIDER_UNAVAILABLE: (ProviderErrorKind.UNAVAILABLE, True),
    ProviderErrorCode.TRANSPORT_ERROR: (ProviderErrorKind.TRANSPORT, True),
    ProviderErrorCode.STALE_DATA: (ProviderErrorKind.UNAVAILABLE, False),
    ProviderErrorCode.INCOMPLETE_DATA: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.UNKNOWN_PROVIDER_ERROR: (ProviderErrorKind.UNKNOWN, False),
}


@pytest.mark.parametrize(("code", "expected"), EXPECTED_POLICY.items())
def test_every_diagnostic_code_has_frozen_parent_kind_and_retryability(
    code: ProviderErrorCode, expected: tuple[ProviderErrorKind, bool]
) -> None:
    error = normalized_provider_error(
        code, "safe diagnostic", "fixture", MarketCapability.REAL_TIME_QUOTE_V1
    )
    assert (error.kind, error.retryable) == expected
    assert dataclasses.is_dataclass(error) and error.__dataclass_params__.frozen


def test_error_policy_cannot_be_fabricated() -> None:
    with pytest.raises(ValueError, match="policy is inconsistent"):
        NormalizedProviderError(
            ProviderErrorKind.UNKNOWN,
            ProviderErrorCode.AUTHENTICATION_FAILED,
            True,
            "safe",
            "fixture",
            MarketCapability.REAL_TIME_QUOTE_V1,
        )


def test_validation_check_status_remains_closed() -> None:
    assert {value.value for value in ValidationCheckStatus} == {
        "pass",
        "fail",
        "skipped",
        "not_supported",
    }


def test_provider_contract_contains_only_read_lifecycle_operations() -> None:
    names = set(MarketDataProvider.__dict__)
    assert {"provider_id", "metadata", "capabilities", "fetch", "health", "validate", "shutdown"} <= names
    assert not names & {"submit", "place_order", "modify", "cancel", "transfer", "authenticate"}
