"""Provider-shaped Tradier fake for fixed index/ETF subjects (SPX, SPY).

Serves quotes, daily history, expirations and greeks-bearing chains in
Tradier's wire shape so the real fixed-subject composition root can run end
to end without network. Index quotes carry no bid/ask, like Tradier's.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from market_data.transport import ReadOnlyHttpRequest, ReadOnlyHttpResponse

SPOT = {"SPX": 5700.0, "SPY": 570.0}


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


class IndexTradierFixture:
    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)
        self.requests: list[ReadOnlyHttpRequest] = []

    def _ms(self) -> int:
        return int(self.now.timestamp() * 1000)

    def _chain(self, symbol: str, expiration: date) -> dict[str, object]:
        spot, step = SPOT[symbol], (25 if symbol == "SPX" else 1)
        monthly = expiration == _third_friday(expiration.year, expiration.month)
        root = (symbol if monthly else f"{symbol}W") if symbol == "SPX" else symbol
        rows = []
        for offset in range(-30, 31):
            strike = round(spot + offset * step, 2)
            for option_type in ("call", "put"):
                moneyness = (spot - strike) / spot
                call_delta = max(0.02, min(0.98, 0.5 + moneyness * 8))
                delta = call_delta if option_type == "call" else call_delta - 1
                in_money = (option_type == "call") == (strike < spot)
                mid = max(0.5, abs(spot - strike) * (0.6 if in_money else 0.05) + 20)
                rows.append(
                    {
                        "symbol": f"{root}{expiration:%y%m%d}{option_type[0].upper()}"
                        f"{int(strike * 1000):08d}",
                        "underlying": symbol,
                        "root_symbol": root,
                        "option_type": option_type,
                        "expiration_date": expiration.isoformat(),
                        "strike": strike,
                        "bid": round(mid * 0.98, 2),
                        "ask": round(mid * 1.02, 2),
                        "last": round(mid, 2),
                        "volume": 100,
                        "open_interest": 1000,
                        "trade_date": self._ms(),
                        "greeks": {
                            "delta": delta,
                            "gamma": 0.001,
                            "theta": -1.0,
                            "vega": 2.0,
                            "rho": 0.1,
                            "mid_iv": 0.15,
                            "updated_at": self.now.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    }
                )
        return {"options": {"option": rows}}

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        query = dict(request.query)
        symbol = query.get("symbol") or query.get("symbols") or ""
        body: dict[str, object]
        if request.path.endswith("/quotes"):
            index = symbol == "SPX"
            body = {
                "quotes": {
                    "quote": {
                        "symbol": symbol,
                        "last": SPOT[symbol],
                        "bid": None if index else SPOT[symbol] - 0.01,
                        "ask": None if index else SPOT[symbol] + 0.01,
                        "bidsize": 0,
                        "asksize": 0,
                        "volume": 0,
                        "trade_date": self._ms(),
                    }
                }
            }
        elif request.path.endswith("/history"):
            days, cursor = [], self.now.date() - timedelta(days=60)
            while cursor < self.now.date():
                if cursor.weekday() < 5:
                    price = SPOT[symbol]
                    days.append(
                        {
                            "date": cursor.isoformat(),
                            "open": price,
                            "high": price * 1.01,
                            "low": price * 0.99,
                            "close": price,
                            "volume": 1000,
                        }
                    )
                cursor += timedelta(days=1)
            body = {"history": {"day": days}}
        elif request.path.endswith("/expirations"):
            dates, cursor = [], self.now.date()
            while cursor <= self.now.date() + timedelta(days=80):
                if cursor.weekday() < 5:
                    dates.append(cursor.isoformat())
                cursor += timedelta(days=1)
            body = {"expirations": {"date": dates}}
        else:
            body = self._chain(symbol, date.fromisoformat(query["expiration"]))
        return ReadOnlyHttpResponse(200, body, (("X-Ratelimit-Available", "119"),), 5, "fixture")
