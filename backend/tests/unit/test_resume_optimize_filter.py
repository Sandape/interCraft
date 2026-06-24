"""Unit tests for M16 snapshot_node per-patch filtering.

Covers the `_filter_patches` helper inside
`app.agents.nodes.resume_optimize.snapshot`, which implements
US5 per-patch accept/reject.
"""
from app.agents.nodes.resume_optimize.snapshot import _filter_patches


def test_filter_patches_none_returns_all():
    patches = [
        {"op": "replace", "path": "/a"},
        {"op": "add", "path": "/b"},
        {"op": "remove", "path": "/c"},
    ]
    assert _filter_patches(patches, None) == patches


def test_filter_patches_empty_list_returns_empty():
    assert _filter_patches([], [0, 1]) == []


def test_filter_patches_filters_by_indices():
    patches = [
        {"op": "replace", "path": "/a"},
        {"op": "replace", "path": "/b"},
        {"op": "add", "path": "/c"},
    ]
    accepted = _filter_patches(patches, [0, 2])
    assert accepted == [patches[0], patches[2]]


def test_filter_patches_out_of_range_ignored():
    patches = [{"op": "replace", "path": "/a"}]
    accepted = _filter_patches(patches, [0, 5, 99])
    assert accepted == patches


def test_filter_patches_empty_accepted_returns_empty():
    patches = [{"op": "replace", "path": "/a"}]
    accepted = _filter_patches(patches, [])
    assert accepted == []
