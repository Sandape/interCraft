"""Contract test fixtures package.

REQ-033 had historical fixture factories in
``tests.contract.fixtures.test_033_fixtures``; those were deleted during
the v1 freeze because they referenced admin/telemetry model names that
have since been renamed (see ``docs/acceptance/v1-production-freeze.md``).
Replacement factories live next to the consuming contract tests.
"""
from __future__ import annotations
