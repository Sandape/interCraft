from __future__ import annotations

from typing import Any

V3_DERIVE_THEME_IDS = {
    "muji-default-autumn",
    "muji-minimal-color",
    "muji-flat-atmospheric",
}

LEGACY_DERIVE_THEME_MAP = {
    "pikachu": "muji-default-autumn",
    "onyx": "muji-minimal-color",
    "bronzor": "muji-flat-atmospheric",
}


def normalize_derive_theme_id(value: str | None) -> str:
    theme_id = (value or "muji-default-autumn").strip()
    if theme_id in V3_DERIVE_THEME_IDS:
        return theme_id
    if theme_id in LEGACY_DERIVE_THEME_MAP:
        return LEGACY_DERIVE_THEME_MAP[theme_id]
    raise ValueError(f"Unsupported derive theme: {theme_id}")


def apply_derive_theme(data: dict[str, Any], theme_id: str) -> dict[str, Any]:
    normalized = normalize_derive_theme_id(theme_id)
    metadata = data.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        data["metadata"] = metadata
    markdown = metadata.setdefault("markdown", {})
    if not isinstance(markdown, dict):
        markdown = {}
        metadata["markdown"] = markdown
    markdown["themeId"] = normalized
    return data


__all__ = [
    "LEGACY_DERIVE_THEME_MAP",
    "V3_DERIVE_THEME_IDS",
    "apply_derive_theme",
    "normalize_derive_theme_id",
]
