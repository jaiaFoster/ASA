"""Position Proposal Engine errors."""


class PositionProposalError(ValueError):
    """Base error for invalid proposal inputs or outputs."""


class InvalidProposalParameterError(PositionProposalError):
    """The effective deterministic sizing policy is invalid."""
