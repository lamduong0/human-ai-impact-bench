"""Canonical digests for benchmark records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def record_digest(record: dict[str, Any]) -> str:
    """Return the SHA-256 digest of canonical scenario JSON."""
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()
