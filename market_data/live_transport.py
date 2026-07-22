"""Stdlib-only live HTTP transport (LIVE-002).

An independent copy of backend/src/asa/market_data_ops/transport.py's
UrllibReadOnlyHttpTransport, for callers of the root-level market_data/
package (e.g. screening/'s --live CLI path) -- backend/ is a separate
deployable service that itself vendors independent copies of market_data/
domain (per its own pyproject.toml comment), so root-level callers cannot
import backend/'s transport and need their own. Same behavior: fixed,
provider-official documented base URLs only, never inferred from the
request; no logic beyond translating the ReadOnlyHttpTransport port to
stdlib urllib.

Deliberately not in screening/: that package's own architecture boundary
tests (tests/architecture/test_screening_boundaries.py) forbid it from
importing urllib or performing network I/O directly -- transport
implementations must be supplied to it from outside, never written inside
it. market_data/ carries no such restriction (only its narrower replay/
fixture submodule does), so this lives alongside market_data/transport.py,
the port it implements.
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
        http_request = urllib.request.Request(url, headers=dict(request.headers), method="GET")
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


def build_live_transport(provider_id: str) -> UrllibReadOnlyHttpTransport:
    if provider_id == "tradier":
        return UrllibReadOnlyHttpTransport(_TRADIER_BASE_URLS)
    if provider_id == "finnhub":
        return UrllibReadOnlyHttpTransport({"production": _FINNHUB_BASE_URL})
    if provider_id == "alpha_vantage":
        return UrllibReadOnlyHttpTransport({"production": _ALPHA_VANTAGE_BASE_URL})
    raise ValueError(f"No live transport configured for provider {provider_id!r}")
