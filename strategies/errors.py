"""Strategy engine and registry errors (ASA-CORE-005)."""

from __future__ import annotations


class StrategyError(Exception):
    """Base error for all strategy operations."""


# ---------------------------------------------------------------------------
# Evaluation errors
# ---------------------------------------------------------------------------


class MissingIndicatorInputError(StrategyError):
    """A required named indicator input was not supplied to the strategy."""

    def __init__(self, strategy_id: str, missing_key: str) -> None:
        super().__init__(f"{strategy_id}: missing required indicator input {missing_key!r}")
        self.strategy_id = strategy_id
        self.missing_key = missing_key


class InvalidStrategyParameterError(StrategyError):
    """A required strategy parameter is missing or has an invalid value/type."""

    def __init__(self, strategy_id: str, message: str) -> None:
        super().__init__(f"{strategy_id}: {message}")
        self.strategy_id = strategy_id


class NoContributingFactsError(StrategyError):
    """A strategy was evaluated with zero contributing Canonical Facts.

    Every Opportunity requires non-empty Evidence (ADR-003); a strategy
    cannot report evidence_confidence or capital_required without at least
    one Canonical Fact backing it.
    """

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"{strategy_id}: no contributing facts supplied")
        self.strategy_id = strategy_id


# ---------------------------------------------------------------------------
# Registry errors
# ---------------------------------------------------------------------------


class DuplicateStrategyRegistrationError(StrategyError):
    """A strategy_id was registered more than once."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"strategy_id already registered: {strategy_id!r}")
        self.strategy_id = strategy_id


class UnknownStrategyIdError(StrategyError):
    """No calculation is registered for the requested strategy_id."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"no strategy registered for id: {strategy_id!r}")
        self.strategy_id = strategy_id


# ---------------------------------------------------------------------------
# Manifest errors
# ---------------------------------------------------------------------------


class ManifestValidationError(StrategyError, ValueError):
    """A Strategy Manifest violates the frozen v1 schema."""


class UnsupportedManifestSchemaError(ManifestValidationError):
    """A manifest uses a schema version this runtime does not support."""


class ManifestSerializationError(ManifestValidationError):
    """A manifest cannot be decoded from canonical JSON data."""


class ComponentContractError(StrategyError, ValueError):
    """A Component Type violates the frozen ASA-ARCH-003 contract."""


class ExpressionError(StrategyError):
    """Base deterministic ASA Expression Language error."""

    def __init__(self, phase: str, code: str, message: str, path: str = "$") -> None:
        super().__init__(f"{phase}:{code}:{path}: {message}")
        self.phase = phase
        self.code = code
        self.path = path


class ExpressionCompileError(ExpressionError):
    """A source expression cannot compile under ASA-ARCH-004."""

    def __init__(self, code: str, message: str, path: str = "$") -> None:
        super().__init__("compile", code, message, path)


class ExpressionEvaluationError(ExpressionError):
    """A compiled expression deterministically failed evaluation."""

    def __init__(self, code: str, message: str, path: str = "$") -> None:
        super().__init__("runtime", code, message, path)
