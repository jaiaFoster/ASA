"""Presentation Layer (ADR-003, ADR-004).

Owns summarization and user-facing output; the only module permitted to
invoke a language model. NARROWED dependency rule (ADR-004): may depend
ONLY on ranking and domain — never on guardrails, strategies, indicators,
facts, observation, or providers.
"""
