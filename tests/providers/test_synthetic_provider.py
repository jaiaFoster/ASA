"""ASA-CORE-002: deterministic synthetic provider tests."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from domain.values import is_normalized_value
from observation import observation_identity
from observation.canonicalization import canonicalize_value
from providers.synthetic import (
    OBSERVATION_TYPE_MARKET_PRICE,
    SYNTHETIC_PROVIDER,
    DeterministicMarketPriceProvider,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EFFECTIVE = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
RECORDED = datetime(2026, 7, 21, 14, 31, tzinfo=timezone.utc)


def _provider() -> DeterministicMarketPriceProvider:
    return DeterministicMarketPriceProvider(identity=observation_identity)


def _price(provider=None):
    provider = provider or _provider()
    return provider.market_price(
        symbol="AAPL", price="201.55", currency="USD",
        effective_time=EFFECTIVE, recorded_time=RECORDED,
    )


class TestRepeatability:
    def test_repeated_input_produces_equal_records(self):
        assert _price() == _price()

    def test_repeated_input_produces_identical_ids(self):
        assert _price().observation_id == _price().observation_id

    def test_two_provider_instances_agree(self):
        assert _price(_provider()) == _price(_provider())

    def test_different_price_different_id(self):
        p = _provider()
        a = p.market_price(symbol="AAPL", price="201.55", currency="USD",
                           effective_time=EFFECTIVE, recorded_time=RECORDED)
        b = p.market_price(symbol="AAPL", price="201.56", currency="USD",
                           effective_time=EFFECTIVE, recorded_time=RECORDED)
        assert a.observation_id != b.observation_id


class TestOutputShape:
    def test_stable_provider_identity(self):
        obs = _price()
        assert obs.provider_id == SYNTHETIC_PROVIDER.provider_id == "synthetic-deterministic"

    def test_observation_type(self):
        assert _price().observation_type == OBSERVATION_TYPE_MARKET_PRICE == "market_price"

    def test_value_is_canonical_normalized(self):
        obs = _price()
        assert is_normalized_value(obs.value)
        assert obs.value == canonicalize_value(obs.value)  # already in canonical order
        assert obs.value == (
            ("currency", "USD"), ("price", Decimal("201.55")), ("symbol", "AAPL"))

    def test_price_is_decimal_not_float(self):
        price = dict(_price().value)["price"]
        assert isinstance(price, Decimal)

    def test_timestamps_are_timezone_aware(self):
        obs = _price()
        assert obs.effective_time.tzinfo is not None
        assert obs.recorded_time.tzinfo is not None

    def test_id_matches_identity_function(self):
        obs = _price()
        assert obs.observation_id == observation_identity(
            obs.provider_id, obs.observation_type, obs.effective_time, obs.value)


class TestProviderPurity:
    def _source(self) -> str:
        return (REPO_ROOT / "providers" / "synthetic" /
                "deterministic_provider.py").read_text()

    def test_no_repository_mutation(self):
        """The provider imports no repository and calls no append/store."""
        src = self._source()
        assert "repository" not in src.lower().replace(
            "no repository writes", "").replace("repository writes", "").replace(
            "any repository", "")
        tree = ast.parse(src)
        calls = [n.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute)]
        assert "append" not in calls

    def test_no_network_access(self):
        """No networking, randomness, or process modules are imported."""
        tree = ast.parse(self._source())
        forbidden = {"socket", "http", "urllib", "requests", "random",
                     "secrets", "uuid", "subprocess", "os"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & forbidden), f"forbidden imports: {imported & forbidden}"

    def test_provider_does_not_import_observation_layer(self):
        """ADR-004: providers/ may depend only on providers and domain."""
        tree = ast.parse(self._source())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "observation" not in imported
