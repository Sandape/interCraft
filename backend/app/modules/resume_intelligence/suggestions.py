"""Safe JSON-patch preview tokens and deterministic inverse patches."""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import get_settings
from app.modules.resume_intelligence.snapshots import canonical_hash


class SuggestionPatchError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


_ALLOWED_PREFIXES = (
    "/summary/content",
    "/sections/",
    "/metadata/markdown/sourceMarkdown",
)


def validate_patch(operations: list[dict[str, Any]]) -> None:
    for operation in operations:
        if operation.get("op") not in {"add", "remove", "replace"}:
            raise SuggestionPatchError("PATCH_REJECTED", "Unsupported patch operation.")
        path = str(operation.get("path") or "")
        if not path.startswith(_ALLOWED_PREFIXES) or "__" in path:
            raise SuggestionPatchError("PATCH_REJECTED", "Patch path is not allowlisted.")
        if operation["op"] != "remove" and "value" not in operation:
            raise SuggestionPatchError("PATCH_REJECTED", "Patch value is required.")


def _parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise SuggestionPatchError("PATCH_REJECTED", "Invalid JSON pointer.")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _parent(document: Any, path: str) -> tuple[Any, str]:
    parts = _parts(path)
    node = document
    for part in parts[:-1]:
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as exc:
                raise SuggestionPatchError("PATCH_REJECTED", "List anchor is stale.") from exc
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise SuggestionPatchError("PATCH_REJECTED", "Object anchor is stale.")
    return node, parts[-1]


def apply_patch(
    document: dict[str, Any], operations: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_patch(operations)
    output = copy.deepcopy(document)
    inverse: list[dict[str, Any]] = []
    for operation in operations:
        parent, key = _parent(output, str(operation["path"]))
        exists = False
        previous: Any = None
        if isinstance(parent, list):
            try:
                index = int(key)
            except ValueError as exc:
                raise SuggestionPatchError("PATCH_REJECTED", "Invalid list index.") from exc
            exists = 0 <= index < len(parent)
            if exists:
                previous = copy.deepcopy(parent[index])
            if operation["op"] == "add" and index == len(parent):
                parent.append(copy.deepcopy(operation["value"]))
            elif operation["op"] == "remove" and exists:
                parent.pop(index)
            elif operation["op"] in {"add", "replace"} and exists:
                parent[index] = copy.deepcopy(operation["value"])
            else:
                raise SuggestionPatchError("PATCH_REJECTED", "List anchor is stale.")
        elif isinstance(parent, dict):
            exists = key in parent
            if exists:
                previous = copy.deepcopy(parent[key])
            if operation["op"] == "remove":
                if not exists:
                    raise SuggestionPatchError("PATCH_REJECTED", "Object anchor is stale.")
                del parent[key]
            elif operation["op"] == "replace":
                if not exists:
                    raise SuggestionPatchError("PATCH_REJECTED", "Object anchor is stale.")
                parent[key] = copy.deepcopy(operation["value"])
            else:
                parent[key] = copy.deepcopy(operation["value"])
        else:
            raise SuggestionPatchError("PATCH_REJECTED", "Invalid patch parent.")

        inverse_op = (
            {"op": "replace", "path": operation["path"], "value": previous}
            if exists
            else {"op": "remove", "path": operation["path"]}
        )
        inverse.insert(0, inverse_op)
    return output, inverse


def find_conflicts(operations: list[dict[str, Any]]) -> list[str]:
    paths = [str(operation.get("path") or "") for operation in operations]
    conflicts: set[str] = set()
    for index, path in enumerate(paths):
        for other in paths[index + 1 :]:
            if path == other or path.startswith(other + "/") or other.startswith(path + "/"):
                conflicts.update({path, other})
    return sorted(conflicts)


def issue_preview_token(payload: dict[str, Any], *, ttl_seconds: int = 600) -> str:
    claims = {**payload, "exp": int(time.time()) + ttl_seconds}
    raw = json.dumps(claims, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(
        get_settings().jwt_secret.encode(), encoded, hashlib.sha256
    ).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_preview_token(token: str) -> dict[str, Any]:
    try:
        encoded_text, signature_text = token.split(".", 1)
        encoded = encoded_text.encode()
        expected = hmac.new(
            get_settings().jwt_secret.encode(), encoded, hashlib.sha256
        ).digest()
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        canonical_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        if not hmac.compare_digest(canonical_signature, signature_text):
            raise SuggestionPatchError("STALE_PREVIEW", "Preview signature is invalid.")
        if not hmac.compare_digest(expected, signature):
            raise SuggestionPatchError("STALE_PREVIEW", "Preview signature is invalid.")
        raw = base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4))
        payload = json.loads(raw)
        if int(payload.get("exp") or 0) < int(time.time()):
            raise SuggestionPatchError("PREVIEW_EXPIRED", "Preview has expired.")
        return payload
    except SuggestionPatchError:
        raise
    except Exception as exc:
        raise SuggestionPatchError("STALE_PREVIEW", "Preview token is invalid.") from exc


def patch_digest(operations: list[dict[str, Any]]) -> str:
    return canonical_hash(operations)
