"""Brief discovery: stable identity, content hashes, source roots."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Canonical root first. ``briefs/`` is where the daily producer task has historically
# written; it is scanned as a fallback so a producer/consumer path mismatch cannot
# silently starve triage. On an id collision the canonical root wins.
SOURCE_ROOTS = ("claude-morning-briefs", "briefs")
BRIEF_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9]+)?)\.md$")


@dataclass(frozen=True)
class Brief:
    brief_id: str  # stable identity: filename stem, independent of content
    path: str  # repo-relative posix path
    sha256: str  # content hash, detects revisions


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover(root: Path = ROOT, source_roots: tuple[str, ...] = SOURCE_ROOTS) -> list[Brief]:
    """Return briefs sorted oldest-first by id; canonical root wins collisions."""
    found: dict[str, Brief] = {}
    for rel in source_roots:
        directory = root / rel
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            match = BRIEF_FILE.fullmatch(path.name)
            if not match or not path.is_file():
                continue
            brief_id = match.group(1)
            if brief_id in found:
                continue
            found[brief_id] = Brief(
                brief_id=brief_id,
                path=path.relative_to(root).as_posix(),
                sha256=sha256_bytes(path.read_bytes()),
            )
    return [found[key] for key in sorted(found)]
