"""REQ-061 US11 eval-fixture factory package (FR-112).

Programmatic generators that produce versioned eval cases for every capability
and ``case_class`` defined in :mod:`app.eval.capability_registry`.

Why programmatic (rather than hand-written JSON):
- Programmatic variants extend coverage to FR-112 thresholds (≥30 ordinary,
  ≥50 write/fact/charging) by varying input space, language, expected_contains
  and class, while keeping fixture size bounded.

Layering::

    app.eval.capability_registry.CapabilityRegistry  ← thresholds + classes
            │
            ▼
    tests.eval._gen.registry.TierPlan  ← per-capability fill targets
            │
            ▼
    tests.eval._gen.factories.<capability>(...)  ← per-cap builders
            │
            ▼
    tests.eval._gen.expansion.expand_all_capabilities()  ← list[dict]
            │
            ▼
    tests.eval.test_061_eval_dataset_coverage  ← assertions + INDEX sync

This module deliberately lives in ``tests/eval/_gen`` (not in ``app/eval``)
because programmatic expansion is test-time only — the production runtime
reads the 13 seed JSON directly via :func:`_load_fixtures`.

Public API::

    from tests.eval._gen.expansion import expand_all_capabilities
    from tests.eval._gen.registry import TIER_PLAN

How to apply:
- Add a new capability? Add a builder in ``factories.py`` + an entry in
  ``TIER_PLAN``; INDEX.yaml will pick it up via ``test_061_eval_dataset_coverage``.
- Lowered threshold? Update ``MIN_ACTIVE_CASES_DEFAULT`` /
  ``MIN_ACTIVE_CASES_WRITE_FACT`` in :mod:`app.eval.capability_registry`.
"""
