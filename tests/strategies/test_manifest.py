"""STRAT-002: canonical Strategy Manifest schema and identity tests."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from strategies import (
    MANIFEST_IDENTITY_NAMESPACE,
    MANIFEST_IDENTITY_VERSION,
    CapabilityRequirement,
    ComponentReference,
    EdgeSpec,
    EventBinding,
    LifecycleEvent,
    ManifestMetadata,
    ManifestObject,
    ManifestSerializationError,
    ManifestValidationError,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
    UnsupportedManifestSchemaError,
    deserialize_manifest,
    freeze_manifest_value,
    manifest_to_data,
    serialize_manifest,
)


def _manifest() -> StrategyManifest:
    source = NodeSpec(
        node_id="facts",
        component=ComponentReference("asa.core", "FactSource", "1.0.0"),
        parameters=(
            ParameterSpec("instrument", "InstrumentId", "BBG000B9XRY4"),
            ParameterSpec("fact_type", "Text", "market_price"),
        ),
    )
    proposal = NodeSpec(
        node_id="proposal",
        component=ComponentReference("asa.core", "PositionProposal", "1.0.0"),
        parameters=(
            ParameterSpec(
                "rationale",
                "Map.Text",
                {
                    "summary": "price signal",
                    "labels": ["deterministic", "reference"],
                },
            ),
        ),
    )
    return StrategyManifest(
        schema_version="1.0.0",
        strategy_id="reference.momentum",
        strategy_version="1.2.3",
        metadata=ManifestMetadata(
            name="Reference Momentum",
            description="Deterministic reference manifest",
            tags=("reference", "momentum"),
        ),
        parameters=(
            ParameterSpec("window", "Integer", 20),
            ParameterSpec("threshold", "Decimal", "0.0500"),
        ),
        required_capabilities=(
            CapabilityRequirement("emit_opportunity", "1.0.0"),
            CapabilityRequirement("consume_facts", "1.0.0"),
        ),
        nodes=(proposal, source),
        edges=(EdgeSpec("facts", "facts", "proposal", "evidence"),),
        outputs=(OutputSpec("opportunity", "proposal", "opportunity"),),
        events=(
            EventBinding(
                LifecycleEvent.NODE_COMPLETED,
                ("outputs", "evidence"),
                node_id="proposal",
            ),
            EventBinding(LifecycleEvent.EVALUATION_COMPLETED, ("outputs",)),
        ),
    )


class TestManifestSchema:
    def test_complete_schema_round_trips_through_canonical_json(self):
        manifest = _manifest()
        payload = serialize_manifest(manifest)

        assert deserialize_manifest(payload) == manifest
        assert serialize_manifest(deserialize_manifest(payload)) == payload
        assert payload.decode("utf-8") == json.dumps(
            manifest_to_data(manifest),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def test_records_and_nested_values_are_immutable(self):
        manifest = _manifest()
        with pytest.raises(FrozenInstanceError):
            manifest.strategy_id = "changed"  # type: ignore[misc]
        rationale = manifest.nodes[1].parameters[0].value
        assert isinstance(rationale, ManifestObject)
        with pytest.raises(FrozenInstanceError):
            rationale.entries = ()  # type: ignore[misc]

    def test_nested_mapping_keys_are_canonicalized(self):
        value = freeze_manifest_value({"z": 1, "a": {"y": 2, "b": 3}})
        assert isinstance(value, ManifestObject)
        assert tuple(key for key, _ in value.entries) == ("a", "z")
        nested = value.entries[0][1]
        assert isinstance(nested, ManifestObject)
        assert tuple(key for key, _ in nested.entries) == ("b", "y")

    @pytest.mark.parametrize("value", [1.5, float("inf"), float("nan")])
    def test_binary_float_values_are_rejected(self, value: float):
        with pytest.raises(ManifestValidationError, match="floating-point"):
            ParameterSpec("threshold", "Decimal", value)

    def test_decimal_literal_is_preserved_as_string(self):
        manifest = _manifest()
        assert manifest.parameters[0].name == "threshold"
        assert manifest.parameters[0].value == "0.05"
        assert deserialize_manifest(manifest.canonical_json()) == manifest

    def test_date_and_instant_literals_are_canonicalized(self):
        assert ParameterSpec("day", "Date", "2026-07-21").value == "2026-07-21"
        assert ParameterSpec(
            "effective_time", "Instant", "2026-07-21T10:00:00-07:00"
        ).value == "2026-07-21T17:00:00+00:00"

    @pytest.mark.parametrize(
        ("type_ref", "value"),
        [
            ("Decimal", "NaN"),
            ("Decimal", "Infinity"),
            ("Date", "07/21/2026"),
            ("Instant", "2026-07-21T10:00:00"),
        ],
    )
    def test_invalid_canonical_scalar_literals_are_rejected(
        self, type_ref: str, value: str
    ):
        with pytest.raises(ManifestValidationError):
            ParameterSpec("value", type_ref, value)

    @pytest.mark.parametrize(
        "version",
        ["1", "v1", "1.0", "01.0.0", "1.01.0", "1.0.01", "1.0.0-01", "latest", "^1.0.0"],
    )
    def test_invalid_semantic_versions_are_rejected(self, version: str):
        with pytest.raises(ManifestValidationError, match="Semantic Version"):
            ComponentReference("asa.core", "Constant", version)

    @pytest.mark.parametrize("version", ["0.0.0", "1.2.3", "1.0.0-alpha.1", "2.0.0+build.7"])
    def test_valid_semantic_versions_are_accepted(self, version: str):
        assert ComponentReference("asa.core", "Constant", version).version == version

    def test_unsupported_manifest_schema_is_rejected(self):
        with pytest.raises(UnsupportedManifestSchemaError):
            replace(_manifest(), schema_version="2.0.0")

    @pytest.mark.parametrize(
        ("field", "replacement"),
        [
            ("parameters", (ParameterSpec("x", "Integer", 1), ParameterSpec("x", "Integer", 2))),
            (
                "nodes",
                (
                    NodeSpec("same", ComponentReference("asa.core", "Constant", "1.0.0")),
                    NodeSpec("same", ComponentReference("asa.core", "Filter", "1.0.0")),
                ),
            ),
            (
                "outputs",
                (OutputSpec("same", "facts", "a"), OutputSpec("same", "facts", "b")),
            ),
        ],
    )
    def test_duplicate_named_records_are_rejected(self, field: str, replacement: object):
        with pytest.raises(ManifestValidationError, match="duplicate"):
            replace(_manifest(), **{field: replacement})

    def test_duplicate_edges_are_rejected(self):
        edge = EdgeSpec("facts", "facts", "proposal", "evidence")
        with pytest.raises(ManifestValidationError, match="duplicate edges"):
            replace(_manifest(), edges=(edge, edge))

    def test_empty_nodes_and_outputs_are_rejected(self):
        with pytest.raises(ManifestValidationError, match="nodes"):
            replace(_manifest(), nodes=())
        with pytest.raises(ManifestValidationError, match="outputs"):
            replace(_manifest(), outputs=())

    def test_closed_lifecycle_enum_is_enforced_during_decode(self):
        data = manifest_to_data(_manifest())
        events = data["events"]
        assert isinstance(events, list)
        assert isinstance(events[0], dict)
        events[0]["event"] = "arbitrary_callback"
        with pytest.raises(ManifestSerializationError, match="lifecycle event"):
            deserialize_manifest(json.dumps(data))


class TestStrictDeserialization:
    def test_unknown_top_level_field_is_rejected(self):
        data = manifest_to_data(_manifest())
        data["unknown"] = True
        with pytest.raises(ManifestSerializationError, match="unknown fields"):
            deserialize_manifest(json.dumps(data))

    def test_unknown_nested_field_is_rejected(self):
        data = manifest_to_data(_manifest())
        nodes = data["nodes"]
        assert isinstance(nodes, list)
        assert isinstance(nodes[0], dict)
        nodes[0]["import_path"] = "unsafe.module"
        with pytest.raises(ManifestSerializationError, match="unknown fields"):
            deserialize_manifest(json.dumps(data))

    def test_duplicate_json_key_is_rejected(self):
        payload = _manifest().canonical_json().decode("utf-8")
        payload = payload.replace(
            '"schema_version":"1.0.0"',
            '"schema_version":"1.0.0","schema_version":"1.0.0"',
        )
        with pytest.raises(ManifestSerializationError, match="duplicate JSON object key"):
            deserialize_manifest(payload)

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_json_numbers_are_rejected(self, value: str):
        payload = _manifest().canonical_json().decode("utf-8")
        payload = payload.replace('"value":20', f'"value":{value}', 1)
        with pytest.raises(ManifestSerializationError, match="non-finite"):
            deserialize_manifest(payload)

    def test_invalid_utf8_is_rejected(self):
        with pytest.raises(ManifestSerializationError, match="UTF-8 JSON"):
            deserialize_manifest(b"\xff")

    def test_json_array_root_is_rejected(self):
        with pytest.raises(ManifestSerializationError, match="JSON object"):
            deserialize_manifest("[]")


class TestDeterminismAndIdentity:
    def test_identity_contract_is_pinned(self):
        assert MANIFEST_IDENTITY_NAMESPACE == "asa.strategy_manifest"
        assert MANIFEST_IDENTITY_VERSION == "v1"
        assert len(_manifest().manifest_id) == 64
        int(_manifest().manifest_id, 16)

    def test_input_collection_order_does_not_affect_bytes_or_identity(self):
        original = _manifest()
        reordered = replace(
            original,
            parameters=tuple(reversed(original.parameters)),
            required_capabilities=tuple(reversed(original.required_capabilities)),
            nodes=tuple(reversed(original.nodes)),
            events=tuple(reversed(original.events)),
            metadata=replace(original.metadata, tags=tuple(reversed(original.metadata.tags))),
        )
        assert reordered == original
        assert reordered.canonical_json() == original.canonical_json()
        assert reordered.manifest_id == original.manifest_id

    def test_display_metadata_changes_bytes_but_not_identity(self):
        original = _manifest()
        renamed = replace(
            original,
            metadata=ManifestMetadata("Renamed", "New description", ("other",)),
        )
        assert renamed.canonical_json() != original.canonical_json()
        assert renamed.manifest_id == original.manifest_id

    @pytest.mark.parametrize(
        "changed",
        [
            replace(_manifest(), strategy_version="1.2.4"),
            replace(
                _manifest(),
                parameters=(
                    ParameterSpec("threshold", "Decimal", "0.06"),
                    ParameterSpec("window", "Integer", 20),
                ),
            ),
            replace(
                _manifest(),
                outputs=(OutputSpec("decision", "proposal", "opportunity"),),
            ),
        ],
    )
    def test_semantic_changes_change_identity(self, changed: StrategyManifest):
        assert changed.manifest_id != _manifest().manifest_id

    def test_identity_regression_vector(self):
        assert _manifest().manifest_id == (
            "b21c0220af2a47bebf632bd0b9754c0722f125a4f31cc097f67f311a3dcb51e9"
        )

    def test_canonical_json_contains_no_incidental_timestamp_or_path(self):
        payload = _manifest().canonical_json().decode("utf-8")
        assert "created_at" not in payload
        assert "evaluated_at" not in payload
        assert "source_path" not in payload
        assert "import_path" not in payload
