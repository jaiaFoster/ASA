"""Bearer-token authentication for the public Agent Data API
(/api/v1/screening*, API-001, SPRINT-008).

Reuses market_data_ops.auth.token_matches -- the only existing
authentication precedent in this codebase -- with its own, separate
credential. Agent API access and internal operations validation are
different consumers and must never share a token.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request, status
from pydantic import SecretStr

from asa.market_data_ops.auth import token_matches

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def build_agent_authorizer(agent_api_token: SecretStr | None) -> Callable[[Request], None]:
    """Returns a FastAPI dependency enforcing `Authorization: Bearer <token>`.

    Matches market_data_ops's own convention exactly: if no token is
    configured, every request 404s -- hiding the endpoint's existence
    entirely rather than exposing an auth-configuration detail through a
    401/403.
    """

    def _authorize(request: Request) -> None:
        if agent_api_token is None:
            raise _NOT_FOUND
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise _NOT_FOUND
        presented = header[len("Bearer ") :]
        if not token_matches(presented, agent_api_token.get_secret_value()):
            raise _NOT_FOUND

    return _authorize
