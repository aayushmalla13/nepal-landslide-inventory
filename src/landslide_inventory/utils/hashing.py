"""Deterministic hashing helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash(*parts: Any) -> str:
    """Return a deterministic SHA-256 hash for arbitrary JSON-serializable inputs."""

    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
