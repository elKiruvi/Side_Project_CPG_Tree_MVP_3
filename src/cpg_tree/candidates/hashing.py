"""Stable content hashing for candidate and approved artifacts.

Content hashes bind a review decision to the exact semantic content that was
reviewed. They are deterministic: the same content always produces the same
digest, regardless of construction order, and every clinically meaningful
field change produces a different digest. Identity and lifecycle fields
(ids, revision, state, generation metadata) never participate, so renumbering
a candidate does not change what was reviewed.

Canonical serialization reuses the knowledge-model shape for expressions
(``knowledge.serialization.to_dict``) and produces YAML/JSON-safe primitives
only.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final

from cpg_tree.knowledge.serialization import to_dict

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")


def sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_json_dumps(payload: Any) -> str:
    """Serialize a canonical dict deterministically.

    Keys are sorted, separators are fixed, and ASCII is never escaped, so
    equal payloads always produce byte-identical text.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def hash_canonical_dict(payload: dict[str, Any]) -> str:
    """Hash a canonical dict of primitives."""
    return sha256_hex(stable_json_dumps(payload))


def validate_sha256_hex(value: str, field_name: str) -> None:
    """Raise ValueError unless value is a 64-character lowercase hex digest."""
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a 64-character hex digest")


def expression_to_canonical(expression: object) -> dict[str, Any]:
    """Serialize a knowledge expression (Condition/LogicalExpression) canonically."""
    return dict(to_dict(expression))
