"""Canonical immutable Strategy Manifest schema (STRAT-002, ASA-ARCH-003).

This module owns only the serialized strategy definition. It deliberately does
not resolve components, validate graph topology or types, evaluate expressions,
or execute a graph. Those responsibilities belong to later SPRINT-002 tickets.

V1 uses canonical UTF-8 JSON. Decimal, date, and instant parameter literals are
represented by normalized strings and interpreted later from their explicit
``type_ref``; binary floating point is rejected at the manifest boundary.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, NoReturn, TypeAlias, cast

from strategies.errors import (
    ManifestSerializationError,
    ManifestValidationError,
    UnsupportedManifestSchemaError,
)

MANIFEST_IDENTITY_NAMESPACE = "asa.strategy_manifest"
MANIFEST_IDENTITY_VERSION = "v1"
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({"1.0.0"})

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

ManifestScalar: TypeAlias = None | bool | int | str
ManifestValue: TypeAlias = (
    "ManifestScalar | tuple[ManifestValue, ...] | ManifestObject"
)


class LifecycleEvent(str, Enum):
    """Closed lifecycle vocabulary frozen by ASA-ARCH-003."""

    MANIFEST_VALIDATED = "manifest_validated"
    GRAPH_COMPILED = "graph_compiled"
    EVALUATION_STARTED = "evaluation_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    EVALUATION_COMPLETED = "evaluation_completed"
    EVALUATION_FAILED = "evaluation_failed"


@dataclass(frozen=True, slots=True)
class ManifestObject:
    """Immutable JSON object with canonical lexicographic key ordering."""

    entries: tuple[tuple[str, ManifestValue], ...]

    def __post_init__(self) -> None:
        normalized: list[tuple[str, ManifestValue]] = []
        seen: set[str] = set()
        for key, value in self.entries:
            if not isinstance(key, str) or not key:
                raise ManifestValidationError("manifest object keys must be non-empty strings")
            if key in seen:
                raise ManifestValidationError(f"duplicate manifest object key: {key}")
            seen.add(key)
            normalized.append((key, freeze_manifest_value(value)))
        object.__setattr__(self, "entries", tuple(sorted(normalized)))


def freeze_manifest_value(value: object) -> ManifestValue:
    """Convert JSON-compatible input to its immutable manifest representation."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        raise ManifestValidationError(
            "floating-point manifest values are forbidden; use a normalized decimal string"
        )
    if isinstance(value, ManifestObject):
        return value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ManifestValidationError("manifest object keys must be strings")
        return ManifestObject(
            tuple((cast(str, key), freeze_manifest_value(item)) for key, item in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_manifest_value(item) for item in value)
    raise ManifestValidationError(f"unsupported manifest value type: {type(value).__name__}")


def _require_identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ManifestValidationError(
            f"{field_name} must match {_IDENTIFIER_RE.pattern}: {value!r}"
        )


def _require_semver(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _SEMVER_RE.fullmatch(value) is None:
        raise ManifestValidationError(
            f"{field_name} must be a valid Semantic Version: {value!r}"
        )


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ManifestValidationError(f"{field_name} contains duplicate values")


def _canonical_decimal_literal(value: ManifestValue, field_name: str) -> str:
    if not isinstance(value, str):
        raise ManifestValidationError(f"{field_name} must be a decimal string")
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise ManifestValidationError(f"{field_name} is not a valid decimal string") from exc
    if not decimal_value.is_finite():
        raise ManifestValidationError(f"{field_name} must be finite")
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _canonical_date_literal(value: ManifestValue, field_name: str) -> str:
    if not isinstance(value, str):
        raise ManifestValidationError(f"{field_name} must be an ISO-8601 date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestValidationError(f"{field_name} is not a valid ISO-8601 date") from exc
    return parsed.isoformat()


def _canonical_instant_literal(value: ManifestValue, field_name: str) -> str:
    if not isinstance(value, str):
        raise ManifestValidationError(
            f"{field_name} must be a timezone-aware ISO-8601 instant string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestValidationError(f"{field_name} is not a valid ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestValidationError(f"{field_name} must include a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ManifestMetadata:
    """Display-only manifest metadata; excluded from deterministic identity."""

    name: str
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ManifestValidationError("metadata.name must not be empty")
        normalized_tags = tuple(sorted(self.tags))
        if any(not tag.strip() for tag in normalized_tags):
            raise ManifestValidationError("metadata.tags must not contain empty values")
        _require_unique(normalized_tags, "metadata.tags")
        object.__setattr__(self, "tags", normalized_tags)


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One typed, effective strategy or node parameter value."""

    name: str
    type_ref: str
    value: ManifestValue

    def __post_init__(self) -> None:
        _require_identifier(self.name, "parameter.name")
        _require_identifier(self.type_ref, "parameter.type_ref")
        value = freeze_manifest_value(self.value)
        if self.type_ref == "Decimal":
            value = _canonical_decimal_literal(value, f"parameter {self.name}.value")
        elif self.type_ref == "Date":
            value = _canonical_date_literal(value, f"parameter {self.name}.value")
        elif self.type_ref == "Instant":
            value = _canonical_instant_literal(value, f"parameter {self.name}.value")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class ComponentReference:
    """Exact component identity; version ranges and latest-resolution are invalid."""

    namespace: str
    name: str
    version: str

    def __post_init__(self) -> None:
        _require_identifier(self.namespace, "component.namespace")
        _require_identifier(self.name, "component.name")
        _require_semver(self.version, "component.version")


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """One immutable component instance in a Strategy Graph definition."""

    node_id: str
    component: ComponentReference
    parameters: tuple[ParameterSpec, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_identifier(self.node_id, "node.node_id")
        normalized = tuple(sorted(self.parameters, key=lambda item: item.name))
        _require_unique(tuple(item.name for item in normalized), f"node {self.node_id} parameters")
        object.__setattr__(self, "parameters", normalized)


@dataclass(frozen=True, slots=True, order=True)
class EdgeSpec:
    """One directed typed-port connection; type validation occurs during compilation."""

    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str

    def __post_init__(self) -> None:
        _require_identifier(self.source_node_id, "edge.source_node_id")
        _require_identifier(self.source_port, "edge.source_port")
        _require_identifier(self.target_node_id, "edge.target_node_id")
        _require_identifier(self.target_port, "edge.target_port")


@dataclass(frozen=True, slots=True, order=True)
class CapabilityRequirement:
    """An exact capability requirement declared by the strategy."""

    name: str
    version: str

    def __post_init__(self) -> None:
        _require_identifier(self.name, "capability.name")
        _require_semver(self.version, "capability.version")


@dataclass(frozen=True, slots=True)
class EventBinding:
    """Declarative trace-field selection for one closed lifecycle event."""

    event: LifecycleEvent
    explanation_fields: tuple[str, ...] = field(default_factory=tuple)
    node_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event, LifecycleEvent):
            raise ManifestValidationError("event.event must be a supported LifecycleEvent")
        if self.node_id is not None:
            _require_identifier(self.node_id, "event.node_id")
        fields = tuple(sorted(self.explanation_fields))
        for field_name in fields:
            _require_identifier(field_name, "event.explanation_field")
        _require_unique(fields, "event.explanation_fields")
        object.__setattr__(self, "explanation_fields", fields)


@dataclass(frozen=True, slots=True, order=True)
class OutputSpec:
    """One named graph output binding."""

    name: str
    node_id: str
    port: str

    def __post_init__(self) -> None:
        _require_identifier(self.name, "output.name")
        _require_identifier(self.node_id, "output.node_id")
        _require_identifier(self.port, "output.port")


@dataclass(frozen=True, slots=True)
class StrategyManifest:
    """Complete canonical serialized definition of one strategy."""

    schema_version: str
    strategy_id: str
    strategy_version: str
    metadata: ManifestMetadata
    parameters: tuple[ParameterSpec, ...]
    required_capabilities: tuple[CapabilityRequirement, ...]
    nodes: tuple[NodeSpec, ...]
    edges: tuple[EdgeSpec, ...]
    outputs: tuple[OutputSpec, ...]
    events: tuple[EventBinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_semver(self.schema_version, "schema_version")
        if self.schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
            raise UnsupportedManifestSchemaError(
                f"unsupported manifest schema version: {self.schema_version}"
            )
        _require_identifier(self.strategy_id, "strategy_id")
        _require_semver(self.strategy_version, "strategy_version")

        parameters = tuple(sorted(self.parameters, key=lambda item: item.name))
        capabilities = tuple(sorted(self.required_capabilities))
        nodes = tuple(sorted(self.nodes, key=lambda item: item.node_id))
        edges = tuple(sorted(self.edges))
        outputs = tuple(sorted(self.outputs))
        events = tuple(
            sorted(self.events, key=lambda item: (item.event.value, item.node_id or ""))
        )

        _require_unique(tuple(item.name for item in parameters), "manifest.parameters")
        _require_unique(
            tuple(item.name for item in capabilities),
            "manifest.required_capabilities",
        )
        _require_unique(tuple(item.node_id for item in nodes), "manifest.nodes")
        if len(edges) != len(set(edges)):
            raise ManifestValidationError("manifest.edges contains duplicate edges")
        _require_unique(tuple(item.name for item in outputs), "manifest.outputs")
        event_keys = tuple(f"{item.event.value}:{item.node_id or ''}" for item in events)
        _require_unique(event_keys, "manifest.events")

        if not nodes:
            raise ManifestValidationError("manifest.nodes must not be empty")
        if not outputs:
            raise ManifestValidationError("manifest.outputs must not be empty")

        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "events", events)

    @property
    def manifest_id(self) -> str:
        """Deterministic identity over semantic manifest content only."""
        return manifest_identity(self)

    def canonical_json(self) -> bytes:
        """Return canonical UTF-8 JSON bytes for the complete manifest."""
        return serialize_manifest(self)


def _value_to_json(value: ManifestValue) -> object:
    if isinstance(value, ManifestObject):
        return {key: _value_to_json(item) for key, item in value.entries}
    if isinstance(value, tuple):
        return [_value_to_json(item) for item in value]
    return value


def _parameter_to_data(parameter: ParameterSpec) -> dict[str, object]:
    return {
        "name": parameter.name,
        "type_ref": parameter.type_ref,
        "value": _value_to_json(parameter.value),
    }


def _semantic_manifest_data(manifest: StrategyManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "strategy_id": manifest.strategy_id,
        "strategy_version": manifest.strategy_version,
        "parameters": [_parameter_to_data(item) for item in manifest.parameters],
        "required_capabilities": [
            {"name": item.name, "version": item.version}
            for item in manifest.required_capabilities
        ],
        "nodes": [
            {
                "node_id": item.node_id,
                "component": {
                    "namespace": item.component.namespace,
                    "name": item.component.name,
                    "version": item.component.version,
                },
                "parameters": [_parameter_to_data(value) for value in item.parameters],
            }
            for item in manifest.nodes
        ],
        "edges": [
            {
                "source_node_id": item.source_node_id,
                "source_port": item.source_port,
                "target_node_id": item.target_node_id,
                "target_port": item.target_port,
            }
            for item in manifest.edges
        ],
        "outputs": [
            {"name": item.name, "node_id": item.node_id, "port": item.port}
            for item in manifest.outputs
        ],
        "events": [
            {
                "event": item.event.value,
                "node_id": item.node_id,
                "explanation_fields": list(item.explanation_fields),
            }
            for item in manifest.events
        ],
    }


def manifest_to_data(manifest: StrategyManifest) -> dict[str, object]:
    """Return the complete canonical wire representation as built-in values."""
    data = _semantic_manifest_data(manifest)
    data["metadata"] = {
        "name": manifest.metadata.name,
        "description": manifest.metadata.description,
        "tags": list(manifest.metadata.tags),
    }
    return data


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def serialize_manifest(manifest: StrategyManifest) -> bytes:
    """Serialize one manifest to canonical UTF-8 JSON."""
    return _canonical_json_bytes(manifest_to_data(manifest))


def manifest_identity(manifest: StrategyManifest) -> str:
    """Hash namespace, identity version, and semantic manifest content."""
    payload = {
        "identity_namespace": MANIFEST_IDENTITY_NAMESPACE,
        "identity_version": MANIFEST_IDENTITY_VERSION,
        "manifest": _semantic_manifest_data(manifest),
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _require_object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ManifestSerializationError(f"{path} must be a JSON object")
    return cast(dict[str, object], value)


def _require_array(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ManifestSerializationError(f"{path} must be a JSON array")
    return cast(list[object], value)


def _require_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ManifestSerializationError(f"{path} must be a string")
    return value


def _reject_unknown(
    value: dict[str, object], required: set[str], optional: set[str], path: str
) -> None:
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise ManifestSerializationError(
            f"{path} is missing required fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise ManifestSerializationError(
            f"{path} contains unknown fields: {', '.join(sorted(unknown))}"
        )


def _parse_parameter(value: object, path: str) -> ParameterSpec:
    item = _require_object(value, path)
    _reject_unknown(item, {"name", "type_ref", "value"}, set(), path)
    return ParameterSpec(
        name=_require_string(item["name"], f"{path}.name"),
        type_ref=_require_string(item["type_ref"], f"{path}.type_ref"),
        value=freeze_manifest_value(item["value"]),
    )


def _parse_manifest_data(root: dict[str, object]) -> StrategyManifest:
    required = {
        "schema_version",
        "strategy_id",
        "strategy_version",
        "metadata",
        "parameters",
        "required_capabilities",
        "nodes",
        "edges",
        "outputs",
        "events",
    }
    _reject_unknown(root, required, set(), "$")

    metadata_data = _require_object(root["metadata"], "$.metadata")
    _reject_unknown(metadata_data, {"name", "description", "tags"}, set(), "$.metadata")
    metadata = ManifestMetadata(
        name=_require_string(metadata_data["name"], "$.metadata.name"),
        description=_require_string(metadata_data["description"], "$.metadata.description"),
        tags=tuple(
            _require_string(item, f"$.metadata.tags[{index}]")
            for index, item in enumerate(_require_array(metadata_data["tags"], "$.metadata.tags"))
        ),
    )

    parameters = tuple(
        _parse_parameter(item, f"$.parameters[{index}]")
        for index, item in enumerate(_require_array(root["parameters"], "$.parameters"))
    )

    capabilities: list[CapabilityRequirement] = []
    for index, raw in enumerate(
        _require_array(root["required_capabilities"], "$.required_capabilities")
    ):
        path = f"$.required_capabilities[{index}]"
        item = _require_object(raw, path)
        _reject_unknown(item, {"name", "version"}, set(), path)
        capabilities.append(
            CapabilityRequirement(
                name=_require_string(item["name"], f"{path}.name"),
                version=_require_string(item["version"], f"{path}.version"),
            )
        )

    nodes: list[NodeSpec] = []
    for index, raw in enumerate(_require_array(root["nodes"], "$.nodes")):
        path = f"$.nodes[{index}]"
        item = _require_object(raw, path)
        _reject_unknown(item, {"node_id", "component", "parameters"}, set(), path)
        component_data = _require_object(item["component"], f"{path}.component")
        _reject_unknown(
            component_data,
            {"namespace", "name", "version"},
            set(),
            f"{path}.component",
        )
        nodes.append(
            NodeSpec(
                node_id=_require_string(item["node_id"], f"{path}.node_id"),
                component=ComponentReference(
                    namespace=_require_string(
                        component_data["namespace"], f"{path}.component.namespace"
                    ),
                    name=_require_string(component_data["name"], f"{path}.component.name"),
                    version=_require_string(
                        component_data["version"], f"{path}.component.version"
                    ),
                ),
                parameters=tuple(
                    _parse_parameter(value, f"{path}.parameters[{parameter_index}]")
                    for parameter_index, value in enumerate(
                        _require_array(item["parameters"], f"{path}.parameters")
                    )
                ),
            )
        )

    edges: list[EdgeSpec] = []
    for index, raw in enumerate(_require_array(root["edges"], "$.edges")):
        path = f"$.edges[{index}]"
        item = _require_object(raw, path)
        fields = {"source_node_id", "source_port", "target_node_id", "target_port"}
        _reject_unknown(item, fields, set(), path)
        edges.append(
            EdgeSpec(
                source_node_id=_require_string(item["source_node_id"], f"{path}.source_node_id"),
                source_port=_require_string(item["source_port"], f"{path}.source_port"),
                target_node_id=_require_string(item["target_node_id"], f"{path}.target_node_id"),
                target_port=_require_string(item["target_port"], f"{path}.target_port"),
            )
        )

    outputs: list[OutputSpec] = []
    for index, raw in enumerate(_require_array(root["outputs"], "$.outputs")):
        path = f"$.outputs[{index}]"
        item = _require_object(raw, path)
        _reject_unknown(item, {"name", "node_id", "port"}, set(), path)
        outputs.append(
            OutputSpec(
                name=_require_string(item["name"], f"{path}.name"),
                node_id=_require_string(item["node_id"], f"{path}.node_id"),
                port=_require_string(item["port"], f"{path}.port"),
            )
        )

    events: list[EventBinding] = []
    for index, raw in enumerate(_require_array(root["events"], "$.events")):
        path = f"$.events[{index}]"
        item = _require_object(raw, path)
        _reject_unknown(item, {"event", "node_id", "explanation_fields"}, set(), path)
        node_value = item["node_id"]
        if node_value is not None and not isinstance(node_value, str):
            raise ManifestSerializationError(f"{path}.node_id must be a string or null")
        event_text = _require_string(item["event"], f"{path}.event")
        try:
            event = LifecycleEvent(event_text)
        except ValueError as exc:
            raise ManifestSerializationError(
                f"{path}.event is not a supported lifecycle event: {event_text}"
            ) from exc
        events.append(
            EventBinding(
                event=event,
                node_id=node_value,
                explanation_fields=tuple(
                    _require_string(value, f"{path}.explanation_fields[{field_index}]")
                    for field_index, value in enumerate(
                        _require_array(item["explanation_fields"], f"{path}.explanation_fields")
                    )
                ),
            )
        )

    return StrategyManifest(
        schema_version=_require_string(root["schema_version"], "$.schema_version"),
        strategy_id=_require_string(root["strategy_id"], "$.strategy_id"),
        strategy_version=_require_string(root["strategy_version"], "$.strategy_version"),
        metadata=metadata,
        parameters=parameters,
        required_capabilities=tuple(capabilities),
        nodes=tuple(nodes),
        edges=tuple(edges),
        outputs=tuple(outputs),
        events=tuple(events),
    )


def deserialize_manifest(payload: bytes | str) -> StrategyManifest:
    """Parse strict JSON into the immutable v1 Strategy Manifest schema."""
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(
            text,
            parse_constant=_raise_non_finite,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestSerializationError("manifest is not valid UTF-8 JSON") from exc
    return _parse_manifest_data(_require_object(data, "$"))


def _raise_non_finite(value: str) -> NoReturn:
    raise ManifestSerializationError(f"non-finite JSON value is forbidden: {value}")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestSerializationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result
