"""Concrete stdlib-only HTTP transport for the injected ReadOnlyHttpTransport port.

market_data.transport defines the ReadOnlyHttpTransport Protocol but ships no concrete
adapter (only test fakes exist). This is the one missing infrastructure adapter, wired
the same way asa.integrations.postgres wires the repository port -- it performs no
Market Data validation logic itself.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

from market_data.transport import (
    ReadOnlyHttpRequest,
    ReadOnlyHttpResponse,
    ReadOnlyTransportError,
    ReadOnlyTransportTimeout,
)

# Base URLs are provider-official documented hosts only; never inferred from the request.
_TRADIER_BASE_URLS = {
    "sandbox": "https://sandbox.tradier.com",
    "production": "https://api.tradier.com",
}
_FINNHUB_BASE_URL = "https://finnhub.io"
_ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co"


class UrllibReadOnlyHttpTransport:
    """One instance per provider; the base URL is fixed at construction time."""

    def __init__(self, base_urls: dict[str, str]) -> None:
        self._base_urls = dict(base_urls)

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        base_url = self._base_urls.get(request.endpoint_environment)
        if base_url is None:
            raise ReadOnlyTransportError(
                f"No configured base URL for endpoint_environment={request.endpoint_environment!r}"
            )
        query = f"?{urlencode(request.query)}" if request.query else ""
        url = f"{base_url}{request.path}{query}"
        http_request = urllib.request.Request(
            url, headers=dict(request.headers), method="GET"
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed https provider hosts only
                http_request, timeout=request.timeout_seconds
            ) as raw_response:
                status_code = raw_response.status
                body_bytes = raw_response.read()
                response_headers = tuple(raw_response.getheaders())
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            body_bytes = exc.read()
            response_headers = tuple(exc.headers.items()) if exc.headers else ()
        except TimeoutError as exc:
            raise ReadOnlyTransportTimeout("Provider request timed out") from exc
        except urllib.error.URLError as exc:
            raise ReadOnlyTransportError("Provider transport failed") from exc
        latency_milliseconds = int((time.monotonic() - started) * 1000)
        try:
            json_body = json.loads(body_bytes) if body_bytes else {}
        except json.JSONDecodeError as exc:
            raise ReadOnlyTransportError("Provider response was not valid JSON") from exc
        if not isinstance(json_body, dict):
            json_body = {"data": json_body}
        return ReadOnlyHttpResponse(
            status_code,
            json_body,
            response_headers,
            latency_milliseconds,
            f"live-request-{started:.6f}",
        )


def build_transport_for_provider(provider_id: str) -> UrllibReadOnlyHttpTransport:
    if provider_id == "tradier":
        return UrllibReadOnlyHttpTransport(_TRADIER_BASE_URLS)
    if provider_id == "finnhub":
        return UrllibReadOnlyHttpTransport({"production": _FINNHUB_BASE_URL})
    if provider_id == "alpha_vantage":
        return UrllibReadOnlyHttpTransport({"production": _ALPHA_VANTAGE_BASE_URL})
    raise ValueError(f"No transport configured for provider {provider_id!r}")
