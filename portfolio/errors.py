"""Portfolio Engine errors."""


class PortfolioEngineError(ValueError):
    """Base error for deterministic portfolio evaluation."""


class InvalidPortfolioParameterError(PortfolioEngineError):
    """Raised when effective portfolio policy parameters are invalid."""


class DuplicatePolicyRegistrationError(PortfolioEngineError):
    """Raised when a policy name is registered more than once."""


class InvalidPolicyRegistryError(PortfolioEngineError):
    """Raised when the registry does not contain the complete v1 policy set."""


class InvalidPolicyOutcomeError(PortfolioEngineError):
    """Raised when a policy returns incoherent provenance or allocation."""
