"""Canonical immutable input identity helpers."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_jd_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in value.split("\n")]
    normalized = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)


def build_input_fingerprint(
    *,
    operation: str,
    resume_hash: str,
    jd_hash: str | None,
    prompt_version: str,
    schema_version: str,
    scoring_version: str,
) -> str:
    return canonical_hash(
        {
            "operation": operation,
            "resume_hash": resume_hash,
            "jd_hash": jd_hash,
            "prompt_version": prompt_version,
            "schema_version": schema_version,
            "scoring_version": scoring_version,
        }
    )
