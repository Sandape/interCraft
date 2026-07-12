"""REQ-061 — AI Metering ledger facts.

Authoritative module for experience points, usage facts, and variable cost
accounting. PostgreSQL append-only events are the source of truth; OTel and
dashboard projections are never financial authority.

Subpackages (planned):
- ``points`` — grants, FIFO buckets, reserve/settle/release/refund/compensate
- ``usage_cost`` — per-attempt usage, rate/FX lock, adjustments, allocations
- ``reconciliation`` — daily conservation, invoice matching, orphan costs

REQ-062 payment, RMB pricing, purchase, and invoice fulfillment remain out of
scope for this module.
"""

MODULE_NAME = "ai_metering"
VERSION = "0.1.0"

__all__ = ["MODULE_NAME", "VERSION"]
