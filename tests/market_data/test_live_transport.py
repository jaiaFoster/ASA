"""Regression coverage for market_data.live_transport (ARCH-MONOREPO-001 Phase 2A).

Backend previously maintained an independent, untested copy of this module
(backend/src/asa/market_data_ops/transport.py, retired by this same ticket) --
neither copy had a dedicated unit test of its own HTTP-translation behavior.
Consolidating to one canonical implementation now used by two consumers
(screening/'s --live CLI path and backend/) makes a bug here strictly more
consequential than before, so this closes that pre-existing gap rather than
carrying it forward silently.

Exercises the real urllib request/response cycle against a local stdlib HTTP
server -- no mocking -- matching this repository's established preference for
real behavior over mocked behavior (e.g. backend/tests/test_railway_runtime.py
spawning real subprocesses).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from market_data.live_transport import UrllibReadOnlyHttpTransport, build_live_transport
from market_data.transport import ReadOnlyHttpRequest, ReadOnlyTransportError


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # silence test output
        pass

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path.startswith("/not-json"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not json")
            return
        if self.path.startswith("/error"):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"echo": self.path}).encode())


@pytest.fixture
def local_server() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def _request(path: str, query: tuple[tuple[str, str], ...] = ()) -> ReadOnlyHttpRequest:
    return ReadOnlyHttpRequest(
        endpoint_environment="production",
        endpoint_class="quote",
        path=path,
        query=query,
        headers=(),
        timeout_seconds=5,
    )


def test_get_returns_parsed_json_body(local_server: str) -> None:
    transport = UrllibReadOnlyHttpTransport({"production": local_server})
    response = transport.get(_request("/quotes", query=(("symbol", "AAPL"),)))

    assert response.status_code == 200
    assert response.json_body == {"echo": "/quotes?symbol=AAPL"}
    assert response.latency_milliseconds >= 0
    assert response.request_reference.startswith("live-request-")


def test_get_surfaces_http_error_status_and_body(local_server: str) -> None:
    transport = UrllibReadOnlyHttpTransport({"production": local_server})
    response = transport.get(_request("/error"))

    assert response.status_code == 404
    assert response.json_body == {"error": "not found"}


def test_get_raises_on_non_json_body(local_server: str) -> None:
    transport = UrllibReadOnlyHttpTransport({"production": local_server})
    with pytest.raises(ReadOnlyTransportError, match="not valid JSON"):
        transport.get(_request("/not-json"))


def test_get_raises_when_endpoint_environment_unconfigured(local_server: str) -> None:
    transport = UrllibReadOnlyHttpTransport({"production": local_server})
    request = ReadOnlyHttpRequest(
        endpoint_environment="sandbox",
        endpoint_class="quote",
        path="/quotes",
        query=(),
        headers=(),
        timeout_seconds=5,
    )
    with pytest.raises(ReadOnlyTransportError, match="No configured base URL"):
        transport.get(request)


def test_build_live_transport_dispatches_per_provider() -> None:
    assert build_live_transport("tradier")._base_urls.keys() == {"sandbox", "production"}
    assert "production" in build_live_transport("finnhub")._base_urls
    assert "production" in build_live_transport("alpha_vantage")._base_urls


def test_build_live_transport_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="No live transport configured"):
        build_live_transport("unknown_provider")
