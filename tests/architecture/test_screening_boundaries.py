"""SCREEN-002: screening framework architecture validation.

Mirrors test_strategy_boundaries.py's pattern for the new screening/
package: an explicit permitted-import allowlist plus prohibited-import and
no-network/no-persistence/no-provider-access sweeps, so the framework
cannot silently grow a dependency on providers, market_data internals, or
infrastructure.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_INFRASTRUCTURE_MODULES = {
    "sqlite3", "psycopg2", "sqlalchemy", "asyncio", "threading",
    "multiprocessing", "socket", "http", "urllib", "requests",
    "random", "secrets",
}

STDLIB_ALLOWED = {
    "__future__", "abc", "argparse", "collections", "dataclasses", "datetime", "decimal", "enum",
    "hashlib", "json", "logging", "re", "sys", "typing",
}
# "logging" added (SPRINT-011-CLOSEOUT/CLOSE-001): pure stdlib, no network/
# disk/process side channel FORBIDDEN_INFRASTRUCTURE_MODULES above already
# guards against -- this module's own docstring's actual concern is a
# dependency on providers/market_data internals/infrastructure, not
# observability. screening/runner.py needs it to log full (operator-only,
# never persisted or API-exposed) exception detail at its own generic
# except-Exception boundary, matching asa/scheduled_screening.py's own
# existing use of the same pattern.


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _screening_files() -> list[Path]:
    return sorted((REPO_ROOT / "screening").glob("*.py"))


class TestScreeningImportScope:
    """screening/ imports only screening, domain, strategies, analytics,
    market_data, facts, and strategy_runtime (SCREEN-004 adapters wrap
    existing strategies; ANALYTICS-003 context builders use analytics/ for
    Forward Factor's derived inputs; LIVE-001 reuses market_data/'s own
    canonical, provider-neutral acquisition pipeline instead of building a
    new one) -- these dependencies are intentional and one-directional:
    none of strategies/, analytics/, or market_data/ is permitted to
    import screening, enforced separately by their own allowlists
    (test_strategy_boundaries.py, test_analytics_boundaries.py, and
    market_data/'s own existing boundary tests). facts/ is the sanctioned
    CanonicalFact projection layer (test_s14_pr04_boundaries.py already
    forbids facts/canonical_projection.py from importing back into
    screening/, so this stays one-directional too).

    strategy_runtime is the one deliberate exception to one-directional
    layering: SPRINT-014 S14-PR-05's ownership model names screening/ and
    strategy_runtime/ as joint owners of "generic_orchestration" under
    ADR-010, and screening/sealed_earnings_calendar.py -- the acquisition
    orchestrator that assembles a subject's SubjectSealedEvidence
    (strategy_runtime/evidence.py) before RuntimeContext ever sees it --
    is the composition root's supplier for that exact type. This does not
    create a circular *import*: strategy_runtime/adapters/earnings_calendar.py
    (the only strategy_runtime module that imports from screening/) never
    imports screening/sealed_earnings_calendar.py, and
    strategy_runtime/evidence.py never imports screening/ at all.

    market_data/ is the sanctioned canonical acquisition layer, not a raw
    provider SDK -- the raw providers/ package stays prohibited below; no
    provider-specific code may enter screening/ directly.
    """

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_only_permitted_roots(self, py_file: Path) -> None:
        permitted = (
            {
                "screening",
                "domain",
                "strategies",
                "analytics",
                "market_data",
                "facts",
                "strategy_runtime",
            }
            | STDLIB_ALLOWED
        )
        imported = _imported_roots(py_file)
        assert imported <= permitted, (
            f"{py_file.name} imports outside {permitted}: {imported - permitted}"
        )

    def test_strategy_runtime_dependency_is_not_circular(self) -> None:
        """The screening<->strategy_runtime exception above is safe only
        because it never closes an actual import cycle: the acquisition
        orchestrator (screening/sealed_earnings_calendar.py) is never
        imported by the one strategy_runtime module that imports from
        screening/ (strategy_runtime/adapters/earnings_calendar.py), and
        strategy_runtime/evidence.py -- the type screening/ depends on --
        never imports screening/ at all.
        """
        adapter_file = REPO_ROOT / "strategy_runtime" / "adapters" / "earnings_calendar.py"
        adapter_tree = ast.parse(adapter_file.read_text())
        imported_modules = {
            node.module
            for node in ast.walk(adapter_tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "screening.sealed_earnings_calendar" not in imported_modules

        evidence_file = REPO_ROOT / "strategy_runtime" / "evidence.py"
        evidence_roots = _imported_roots(evidence_file)
        assert "screening" not in evidence_roots

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_prohibited_imports_absent(self, py_file: Path) -> None:
        prohibited = {
            "providers", "observation", "ranking",
            "guardrails", "presentation", "simulation", "execution_planning",
        }
        imported = _imported_roots(py_file)
        assert not (imported & prohibited), (
            f"{py_file.name} imports prohibited module(s): {imported & prohibited}"
        )

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_no_infrastructure_dependencies(self, py_file: Path) -> None:
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_no_network_or_persistence(self, py_file: Path) -> None:
        forbidden = {
            "socket", "http", "urllib", "requests", "aiohttp",
            "sqlite3", "sqlalchemy", "psycopg2", "pickle", "shelve",
        }
        imported = _imported_roots(py_file)
        assert not (imported & forbidden)

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_no_random_or_ml_libraries(self, py_file: Path) -> None:
        forbidden = {"random", "sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        imported = _imported_roots(py_file)
        assert not (imported & forbidden)


class TestScreeningRegistryIsClosedAndExplicit:
    def test_registry_requires_explicit_construction(self) -> None:
        from screening.registry import ScreeningRegistry

        assert ScreeningRegistry().registered_ids() == ()

    def test_no_dynamic_discovery_helpers_exposed(self) -> None:
        import screening

        forbidden_names = {"discover", "autoregister", "scan_plugins", "load_plugins"}
        assert not (forbidden_names & set(dir(screening)))
