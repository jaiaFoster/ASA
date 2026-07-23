from __future__ import annotations

from market_data.transport import ReadOnlyHttpRequest, ReadOnlyHttpResponse


class ScriptedTransport:
    """Network-free fake satisfying ReadOnlyHttpTransport for tests."""

    def __init__(self, responses: list[ReadOnlyHttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        return self._responses.pop(0)


def tradier_quote_response() -> ReadOnlyHttpResponse:
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
                    "trade_date": 1753113600000,
                }
            }
        },
        (("X-Ratelimit-Available", "119"),),
        12,
        "tradier-request-1",
    )
