"""Strategy Layer (ADR-003).

Owns deterministic Strategy evaluation and Opportunity production. Narrower
dependency rule (ADR-004, ASA-CORE-005): may depend on strategies,
indicators, facts, reconciliation, and domain — not observation or
providers, even though both sit below strategies in the general pipeline
order (Constitution Law 4: Strategies consume knowledge, they do not
gather it).
"""
from strategies.engine import (
    OPPORTUNITY_IDENTITY_NAMESPACE,
    OPPORTUNITY_IDENTITY_VERSION,
    evaluate_strategy,
    opportunity_identity,
)
from strategies.errors import (
    DuplicateStrategyRegistrationError,
    InvalidStrategyParameterError,
    ManifestSerializationError,
    ManifestValidationError,
    MissingIndicatorInputError,
    NoContributingFactsError,
    StrategyError,
    UnsupportedManifestSchemaError,
    UnknownStrategyIdError,
)
from strategies.manifest import (
    MANIFEST_IDENTITY_NAMESPACE,
    MANIFEST_IDENTITY_VERSION,
    SUPPORTED_MANIFEST_SCHEMA_VERSIONS,
    CapabilityRequirement,
    ComponentReference,
    EdgeSpec,
    EventBinding,
    LifecycleEvent,
    ManifestMetadata,
    ManifestObject,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
    deserialize_manifest,
    freeze_manifest_value,
    manifest_identity,
    manifest_to_data,
    serialize_manifest,
)
from strategies.registry import DEFAULT_REGISTRY, StrategyRegistry
from strategies.signal import StrategySignal

__all__ = [
    "DEFAULT_REGISTRY",
    "DuplicateStrategyRegistrationError",
    "EdgeSpec",
    "EventBinding",
    "InvalidStrategyParameterError",
    "LifecycleEvent",
    "MANIFEST_IDENTITY_NAMESPACE",
    "MANIFEST_IDENTITY_VERSION",
    "ManifestMetadata",
    "ManifestObject",
    "ManifestSerializationError",
    "ManifestValidationError",
    "MissingIndicatorInputError",
    "NoContributingFactsError",
    "NodeSpec",
    "OPPORTUNITY_IDENTITY_NAMESPACE",
    "OPPORTUNITY_IDENTITY_VERSION",
    "OutputSpec",
    "ParameterSpec",
    "SUPPORTED_MANIFEST_SCHEMA_VERSIONS",
    "StrategyError",
    "StrategyManifest",
    "StrategyRegistry",
    "StrategySignal",
    "UnsupportedManifestSchemaError",
    "UnknownStrategyIdError",
    "CapabilityRequirement",
    "ComponentReference",
    "deserialize_manifest",
    "evaluate_strategy",
    "freeze_manifest_value",
    "manifest_identity",
    "manifest_to_data",
    "opportunity_identity",
    "serialize_manifest",
]
