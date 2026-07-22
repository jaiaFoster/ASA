"""Guards against drift between the root market_data/domain packages and their
backend vendor copies (backend/src/market_data, backend/src/domain).

The backend service deploys from `/backend` only (Railway root directory), so the
bounded Market Data validation framework is vendored verbatim rather than
reimplemented. This test fails if the two copies diverge.
"""

from __future__ import annotations

import filecmp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def _python_files(root: Path) -> dict[str, Path]:
    return {
        str(path.relative_to(root)): path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    }


def _assert_package_matches(package_name: str) -> None:
    source_root = REPO_ROOT / package_name
    vendor_root = BACKEND_ROOT / "src" / package_name
    source_files = _python_files(source_root)
    vendor_files = _python_files(vendor_root)
    assert source_files.keys() == vendor_files.keys(), (
        f"{package_name}: vendored file set differs from source "
        f"(only-in-source={set(source_files) - set(vendor_files)}, "
        f"only-in-vendor={set(vendor_files) - set(source_files)})"
    )
    mismatched = [
        name
        for name, source_path in source_files.items()
        if not filecmp.cmp(source_path, vendor_files[name], shallow=False)
    ]
    assert not mismatched, f"{package_name}: vendored copy drifted for {mismatched}"


def test_market_data_vendor_matches_source() -> None:
    _assert_package_matches("market_data")


def test_domain_vendor_matches_source() -> None:
    _assert_package_matches("domain")
