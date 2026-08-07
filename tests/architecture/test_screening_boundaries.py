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
    "hashlib", "json", "logging", "re", "sys", "types", "typing",
}
# "types" added (SPRINT-014 S14-PR-05A): screening/subject_planning.py
# uses types.MappingProxyType to hand out read-only views over resolved
# evidence -- pure stdlib, no infrastructure dependency.
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
    and market_data (SCREEN-004 adapters wrap existing strategies;
    ANALYTICS-003 context builders use analytics/ for Forward Factor's
    derived inputs; LIVE-001 reuses market_data/'s own canonical,
    provider-neutral acquisition pipeline instead of building a new one)
    -- these dependencies are intentional and one-directional: none of
    strategies/, analytics/, market_data/, or facts/ is permitted to
    import screening, enforced separately by their own allowlists
    (test_strategy_boundaries.py, test_analytics_boundaries.py, and
    market_data/'s own existing boundary tests). market_data/ is the
    sanctioned canonical acquisition layer, not a raw provider SDK -- the
    raw providers/ package stays prohibited below; no provider-specific
    code may enter screening/ directly.

    "facts" is deliberately NOT part of the package-wide allowlist
    (SPRINT-014 S14-PR-05A, Architect checkpoint: sixth review --
    "a narrow generic screening composition helper may import facts, but
    its architecture rule should be narrow rather than expanding the
    entire package"). Exactly one file,
    screening/subject_fact_projection.py, gets a narrow, file-scoped
    exception below: it is the only layer with simultaneous access to
    market_data/ (for ResolutionResult/MarketSnapshot, the sealed
    evidence a canonical fact is projected from) and
    facts.canonical_projection.project_canonical_fact() -- strategies/
    can reach facts/ but not market_data/, so this narrow bridge exists
    once rather than being duplicated per strategy. Every other screening
    file, including screening/earnings_calendar_facts.py, stays within
    the general allowlist and reaches this bridge only through
    screening/'s own already-permitted "screening" root. facts/ itself
    still cannot import screening (unchanged, one-directional).
    """

    _NARROW_FACTS_EXCEPTION = {"subject_fact_projection.py"}

    @pytest.mark.parametrize("py_file", _screening_files())
    def test_only_permitted_roots(self, py_file: Path) -> None:
        permitted = {"screening", "domain", "strategies", "analytics", "market_data"} | (
            STDLIB_ALLOWED
        )
        if py_file.name in self._NARROW_FACTS_EXCEPTION:
            permitted = permitted | {"facts"}
        imported = _imported_roots(py_file)
        assert imported <= permitted, (
            f"{py_file.name} imports outside {permitted}: {imported - permitted}"
        )

    def test_only_the_narrow_exception_file_imports_facts(self) -> None:
        """Regression guard against the exception silently widening back
        into a package-wide allowance: every screening/ file other than
        the one named exception must import zero "facts" root, even
        though test_only_permitted_roots alone would not catch a second
        file adding it (it would just fail that second file's own
        assertion with a confusing diff) -- this test names the exact
        expected file set explicitly.
        """
        importers = {
            py_file.name for py_file in _screening_files() if "facts" in _imported_roots(py_file)
        }
        assert importers == self._NARROW_FACTS_EXCEPTION

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
