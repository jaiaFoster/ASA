from __future__ import annotations

from datetime import UTC, datetime

from market_data.transport import ReadOnlyHttpRequest, ReadOnlyHttpResponse


class ScriptedTransport:
    """Network-free fake satisfying ReadOnlyHttpTransport for tests."""

    def __init__(self, responses: list[ReadOnlyHttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(
                "no scripted response for "
                f"{request.endpoint_class} {request.path}; requests="
                f"{[item.endpoint_class for item in self.requests]}"
            )
        return self._responses.pop(0)


def tradier_quote_response() -> ReadOnlyHttpResponse:
    observed_at = datetime.now(UTC)
    return ReadOnlyHttpResponse(
        200,
        {
            "quotes": {
                "quote": {
                    "symbol": "AAPL",
                    "bid": "189.10",
                    "ask": "189.20",
                    "last": "189.15",
                    "bidsize": 1,
                    "asksize": 1,
                    "volume": 100,
                    "trade_date": int(observed_at.timestamp() * 1000),
                }
            }
        },
        (("X-Ratelimit-Available", "119"),),
        12,
        "tradier-request-1",
    )
