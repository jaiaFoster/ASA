from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.requests import Request

from asa.api.agent_auth import build_agent_authorizer


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "headers": raw_headers})


class TestBuildAgentAuthorizer:
    def test_no_token_configured_rejects_every_request_as_404(self) -> None:
        authorize = build_agent_authorizer(None)
        with pytest.raises(HTTPException) as excinfo:
            authorize(_request({"Authorization": "Bearer anything"}))
        assert excinfo.value.status_code == 404

    def test_missing_authorization_header_is_404(self) -> None:
        authorize = build_agent_authorizer(SecretStr("correct-token"))
        with pytest.raises(HTTPException) as excinfo:
            authorize(_request())
        assert excinfo.value.status_code == 404

    def test_wrong_token_is_404(self) -> None:
        authorize = build_agent_authorizer(SecretStr("correct-token"))
        with pytest.raises(HTTPException) as excinfo:
            authorize(_request({"Authorization": "Bearer wrong-token"}))
        assert excinfo.value.status_code == 404

    def test_wrong_auth_scheme_is_404(self) -> None:
        authorize = build_agent_authorizer(SecretStr("correct-token"))
        with pytest.raises(HTTPException) as excinfo:
            authorize(_request({"Authorization": "Basic correct-token"}))
        assert excinfo.value.status_code == 404

    def test_correct_token_is_accepted(self) -> None:
        authorize = build_agent_authorizer(SecretStr("correct-token"))
        authorize(_request({"Authorization": "Bearer correct-token"}))  # does not raise
