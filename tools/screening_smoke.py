"""Secret-safe authenticated screening production smoke.

The bearer token is accepted only through an environment variable. Output
contains request paths and status codes, never headers, bodies, or token values.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class SmokeStep:
    method: str
    path: str
    expected_status: int


STEPS = (
    SmokeStep("GET", "/api/v1/health", 200),
    SmokeStep("GET", "/api/v1/readiness", 200),
    SmokeStep("GET", "/api/v1/capabilities", 200),
    SmokeStep("GET", "/api/v1/screening", 200),
    SmokeStep("POST", "/api/v1/screening/{signal}/{symbol}/refresh", 200),
    SmokeStep("GET", "/api/v1/screening/{signal}/{symbol}", 200),
)


def run_smoke(
    base_url: str,
    token: str,
    signal: str,
    symbol: str,
    *,
    opener: Callable[..., object] = urlopen,
) -> int:
    if not base_url.startswith(("https://", "http://")):
        print("FAIL base URL must use http or https", file=sys.stderr)
        return 2
    if not token:
        print("FAIL configured token is empty", file=sys.stderr)
        return 2
    auth = {"Authorization": f"Bearer {token}"}
    failed = False
    for step in STEPS:
        path = step.path.format(signal=signal, symbol=symbol)
        headers = {} if path in {"/api/v1/health", "/api/v1/readiness"} else auth
        request = Request(
            base_url.rstrip("/") + path,
            headers=headers,
            method=step.method,
            data=b"" if step.method == "POST" else None,
        )
        try:
            response = opener(request, timeout=30)
            status = int(response.status)  # type: ignore[attr-defined]
        except HTTPError as error:
            status = error.code
        except (URLError, TimeoutError):
            status = 0
        outcome = "PASS" if status == step.expected_status else "FAIL"
        print(f"{outcome} {step.method} {path} status={status}")
        failed = failed or outcome == "FAIL"
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--signal", default="skew_momentum")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--token-env", default="ASA_AGENT_API_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    if not token:
        print(
            f"FAIL required token environment variable {args.token_env} is not set",
            file=sys.stderr,
        )
        return 2
    return run_smoke(args.base_url, token, args.signal, args.symbol)


if __name__ == "__main__":
    raise SystemExit(main())
