"""DEPRECATED — update_dimensions re-export shell (US2 FR-005 AC-5.8).

The legacy ``update_dimensions_node`` (which mixed 4 DB writes + WS push
in a single function) has been split into 4 single-responsibility nodes
(US2 AC-5.1–AC-5.4):

- ``update_dim_db`` (``update_dim_db.py``): write to ``ability_dimensions``.
- ``update_history`` (``update_history.py``): write to
  ``ability_dimensions_history``.
- ``update_activities`` (``update_activities.py``): write to ``activities``.
- ``ws_push`` (``ws_push.py``): best-effort WS push for ``agent.final``.
- ``update_dim_error_log`` (``update_dim_error_log.py``): intermediate
  node for ``db_warnings`` logging (AC-5.7).

This module is a **compatibility re-export** so callers that did
``from app.agents.nodes.ability_diagnose.update_dimensions import
update_dimensions_node`` continue to import — but the original function
is NOT re-exported (per US2 R5'' round 3 the old implementation is
removed). Any external caller should reference the 4 split names
directly.

This file exists for the dual-track period (FR-008 / US1 AC-8.3).
The ``DEPRECATED`` marker in this docstring makes the file detectable
by lint / grep checks; release manager tracks the deletion in the
release tag.
"""
from __future__ import annotations

# DEPRECATED: this file is a re-export shell, the implementation has moved.
from app.agents.nodes.ability_diagnose.update_dim_db import update_dim_db_node
from app.agents.nodes.ability_diagnose.update_history import update_history_node
from app.agents.nodes.ability_diagnose.update_activities import (
    update_activities_node,
)
from app.agents.nodes.ability_diagnose.ws_push import ws_push_node

# Compatibility: ``update_dimensions_node`` is intentionally NOT
# re-exported — importing it would mask the split, which is the whole
# point of US2 FR-005.
__all__ = [
    "update_dim_db_node",
    "update_history_node",
    "update_activities_node",
    "ws_push_node",
]