"""Eval suite conftest (Phase 4 - T033).

Provides:
- autouse fixture to reset LLM client singletons between eval tests
  (the runner patches `get_llm_client`, but the module-level singleton
  `_llm_client_singleton` may have been initialized by other tests in the
  same process — reset to None so the patched path takes effect).
- No DB / Redis / FastAPI app setup — eval suite is library-only and
  doesn't touch those (Constitution Principle I: Library-First).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_llm_client_singleton() -> None:
    """Reset the LLM client singletons before and after each eval test.

    The EvalRunner patches `get_llm_client` at the node module level, but
    `app.agents.llm_client` has module-level singletons that may have been
    initialized by other tests. We reset them so the eval stub is the only
    client the node sees during the test.
    """
    import app.agents.llm_client as mod

    saved_real = mod._llm_client_singleton
    saved_mock = mod._mock_client_singleton
    saved_mtime = mod._mock_client_scenario_mtime
    mod._llm_client_singleton = None
    mod._mock_client_singleton = None
    mod._mock_client_scenario_mtime = None
    yield
    mod._llm_client_singleton = saved_real
    mod._mock_client_singleton = saved_mock
    mod._mock_client_scenario_mtime = saved_mtime
