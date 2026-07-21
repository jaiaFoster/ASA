"""Backward-compatible re-export shim (ASA-CORE-004).

Canonicalization moved to ``domain/canonicalization.py`` in ASA-CORE-004 —
see that module's docstring for why. Import from there in new code; this
module is kept only so existing imports of
``observation.canonicalization.*`` continue to work.
"""
from __future__ import annotations

from domain.canonicalization import (
    canonicalize_value,
    serialize_canonical,
)

__all__ = ["canonicalize_value", "serialize_canonical"]
