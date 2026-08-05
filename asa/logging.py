import json
import logging
import re
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

# SPRINT-013 S13-11: every field a call site may legitimately attach via
# logging's own `extra={...}` -- an allowlist, not a blocklist, so an
# unexpected field a future call site adds is dropped by default rather
# than silently escaping unreviewed. `strategy_id` was already being
# passed by screening/runner.py's own exception log line before this
# fix and was silently dropped here -- the call site was already
# correct, only this formatter's own allowlist was incomplete.
_SAFE_EXTRA_FIELDS = (
    "provider_request_id",
    "symbol",
    "provider",
    "run_id",
    "run_step",
    "account_id",
    "strategy_id",
    "subject_identity",
    "screening_cycle_id",
    "pair_evaluation_id",
    "capability_id",
    "capability",
    "component_id",
    "safe_error_code",
    "diagnostic_code",
    "signal_id",
)
_MAX_FIELD_LENGTH = 500
_MAX_TRACEBACK_FRAMES = 5
_MAX_CAUSE_DEPTH = 3

# SPRINT-013 S13-11: a message field is free text -- an exception's own
# str(), or a caller's log message -- that this formatter did not choose
# the shape of, unlike the allowlisted extra fields above. A raised
# exception can legitimately embed a request URL or header fragment
# (e.g. requests/httpx exceptions), so this redacts secret-shaped
# fragments by pattern rather than trusting every possible exception
# message to already be safe.
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_.]+")
_SECRET_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(token|key|secret|password|api[_-]?key|access[_-]?token|authorization)"
    r"\s*[=:]\s*[^\s&\"']+"
)


def _redact_secrets(text: str) -> str:
    text = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", text)
    return _SECRET_KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)


def _bounded(value: str, limit: int = _MAX_FIELD_LENGTH) -> str:
    redacted = _redact_secrets(value)
    return redacted if len(redacted) <= limit else f"{redacted[:limit]}...[truncated]"


def _stack_location(exc_tb: TracebackType | None) -> list[dict[str, object]]:
    """File basename, line, and function only -- never a source line's own
    content and never a local-variable repr, for every frame. Bounded to
    the innermost frames (closest to where the exception was actually
    raised, the most diagnostically useful ones), never the full stack.
    """
    frames = traceback.extract_tb(exc_tb)[-_MAX_TRACEBACK_FRAMES:]
    return [
        {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
        for frame in frames
    ]


def _cause_chain(exc: BaseException) -> list[dict[str, object]]:
    """A bounded summary of __cause__/__context__ chaining (`raise X from Y`
    or an exception raised while handling another) -- type and truncated
    message only per link, capped depth, never each link's own full
    nested traceback (unbounded by construction otherwise).
    """
    chain: list[dict[str, object]] = []
    current = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    while current is not None and len(chain) < _MAX_CAUSE_DEPTH:
        chain.append(
            {"exception_type": type(current).__name__, "exception_message": _bounded(str(current))}
        )
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    return chain


def _exception_detail(
    exc_info: (
        tuple[type[BaseException], BaseException, TracebackType | None]
        | tuple[None, None, None]
    ),
) -> dict[str, object]:
    exc_type, exc_value, exc_tb = exc_info
    detail: dict[str, object] = {
        "exception_type": exc_type.__name__ if exc_type is not None else "UnknownException",
        "exception_message": _bounded(str(exc_value)) if exc_value is not None else "",
        "stack_location": _stack_location(exc_tb),
    }
    if exc_value is not None:
        caused_by = _cause_chain(exc_value)
        if caused_by:
            detail["caused_by"] = caused_by
    return detail


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": _bounded(record.getMessage()),
            "request_id": request_id_context.get(),
        }
        for key in _SAFE_EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = _bounded(str(value)) if isinstance(value, str) else value
        # SPRINT-013 S13-11: exc_info=True on a log call previously produced
        # no exception detail at all in the emitted JSON -- this formatter
        # never read record.exc_info. Every field here is individually
        # bounded and type/location/message only, never a raw traceback
        # string, a full repr(), or an unbounded nested-exception chain.
        if record.exc_info:
            payload.update(_exception_detail(record.exc_info))
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
