"""Injected read-only HTTP transport contracts for Market Data adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable


class ReadOnlyTransportError(RuntimeError):
    """Safe transport failure without response or credential material."""


class ReadOnlyTransportTimeout(ReadOnlyTransportError):
    """The configured read timeout elapsed."""


@dataclass(frozen=True, slots=True, repr=False)
class ReadOnlyHttpRequest:
    endpoint_environment: str
    endpoint_class: str
    path: str
    query: tuple[tuple[str, str], ...]
    headers: tuple[tuple[str, str], ...]
    timeout_seconds: int

    def __post_init__(self) -> None:
        if self.path.startswith("http") or not self.path.startswith("/"):
            raise ValueError("ReadOnlyHttpRequest requires a relative path")
        if self.timeout_seconds <= 0:
            raise ValueError("ReadOnlyHttpRequest timeout must be positive")

    def __repr__(self) -> str:
        return (
            "ReadOnlyHttpRequest(endpoint_environment="
            f"{self.endpoint_environment!r}, endpoint_class={self.endpoint_class!r}, "
            f"path={self.path!r}, query_count={len(self.query)}, headers='[REDACTED]', "
            f"timeout_seconds={self.timeout_seconds})"
        )


@dataclass(frozen=True, slots=True)
class ReadOnlyHttpResponse:
    status_code: int
    json_body: Mapping[str, object]
    headers: tuple[tuple[str, str], ...]
    latency_milliseconds: int
    request_reference: str


@runtime_checkable
class ReadOnlyHttpTransport(Protocol):
    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse: ...
