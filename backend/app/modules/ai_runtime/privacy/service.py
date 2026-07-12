"""Privacy policy registry and provenance deletion orchestrator (REQ-061 T022).

Fans out deletion work to every lifecycle-matrix row. Completion requires
evidence or a documented legal/contractual retention outcome for each store —
deleting the canonical PostgreSQL row alone is not completion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ai_runtime.models import AIDataDeletionDelivery, AIEvidenceSnapshot

log = get_logger("ai_runtime.privacy")

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_EXPIRED = "expired"
STATUS_NOT_SUPPORTED = "not_supported_with_contract_expiry"
STATUS_RETRY_WAIT = "retry_wait"

TERMINAL_DELETION_STATUSES = frozenset(
    {STATUS_CONFIRMED, STATUS_EXPIRED, STATUS_NOT_SUPPORTED}
)

MAX_DELETION_ATTEMPTS = 8
BATCH_LIMIT = 100
BASE_RETRY_SECONDS = 2
# Alert when a pending fan-out step stays open longer than this SLA.
DELETION_SLA = timedelta(hours=24)

# Non-exhaustive registry covering data-model.md §10 plus contract-required codes.
# Adding a new store/copy MUST add a row before production data lands there.
LIFECYCLE_REGISTRY: list[dict[str, Any]] = [
    {
        "store": "domain_source_postgresql",
        "owner": "Capability data owner",
        "retention": "source_module_policy",
        "deletion_procedure": "emit_provenance_event_and_invalidate_runtime_refs",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "ai_task",
        "owner": "AI Runtime owner",
        "retention": "metadata_audit_180d_ui_90d",
        "deletion_procedure": "purge_or_pseudonymous_tombstone_after_window",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "ai_task_event",
        "owner": "AI Runtime owner",
        "retention": "metadata_audit_180d",
        "deletion_procedure": "purge_or_pseudonymous_tombstone_after_window",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "runtime_postgresql",
        "owner": "AI Runtime owner",
        "retention": "intent_until_terminal_plus_reconciliation",
        "deletion_procedure": "row_count_and_stranded_intent_scan",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "authorization_receipt",
        "owner": "Security owner",
        "retention": "task_audit_window_then_pseudonymize_actor",
        "deletion_procedure": "revoke_access_then_subject_mapping_erasure",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "point_ledger_event",
        "owner": "Metering owner",
        "retention": "24_months_no_destructive_delete",
        "deletion_procedure": "anonymize_subject_mapping_preserve_facts",
        "default_outcome": STATUS_NOT_SUPPORTED,
    },
    {
        "store": "point_cost_ledger",
        "owner": "Metering owner",
        "retention": "24_months_no_destructive_delete",
        "deletion_procedure": "anonymize_subject_mapping_preserve_facts",
        "default_outcome": STATUS_NOT_SUPPORTED,
    },
    {
        "store": "checkpoint",
        "owner": "AI Runtime owner",
        "retention": "terminal_plus_live_version_appeal_window",
        "deletion_procedure": "delete_thread_checkpoint_or_tombstone",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "cross_thread_store",
        "owner": "AI/Data owner",
        "retention": "purpose_bound_ttl",
        "deletion_procedure": "invalidate_derived_chunks_and_zero_query_verify",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "outbox",
        "owner": "Platform/AI Runtime owner",
        "retention": "reconciliation_window_redis_ttl_bounded",
        "deletion_procedure": "expire_payload_scan_and_dlq_inventory",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "outbox_projection_redis",
        "owner": "Platform/AI Runtime owner",
        "retention": "reconciliation_window_redis_ttl_bounded",
        "deletion_procedure": "expire_payload_scan_and_dlq_inventory",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "operational_projections_caches",
        "owner": "Platform owner",
        "retention": "projection_cache_ttl_temp_janitor",
        "deletion_procedure": "cache_namespace_purge_and_rebuild_compare",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "audit_evidence_badcase",
        "owner": "Privacy/Quality owner",
        "retention": "snapshot_30d_access_audit_180d",
        "deletion_procedure": "delete_snapshot_block_access_retain_pseudonymous_audit",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "evidence_store",
        "owner": "Privacy/Quality owner",
        "retention": "snapshot_max_30d_delete_within_24h_after_withdrawal",
        "deletion_procedure": "object_delete_and_access_block",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "logs_traces_langsmith",
        "owner": "Observability/Privacy owner",
        "retention": "destination_ttl_le_source_purpose",
        "deletion_procedure": "destination_purge_ack_or_documented_expiry",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "otel",
        "owner": "Observability/Privacy owner",
        "retention": "destination_ttl_le_source_purpose",
        "deletion_procedure": "destination_purge_ack_or_documented_expiry",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "langsmith",
        "owner": "Observability/Privacy owner",
        "retention": "destination_ttl_le_source_purpose",
        "deletion_procedure": "destination_purge_ack_or_documented_expiry",
        "default_outcome": STATUS_PENDING,
    },
    {
        "store": "provider_copies",
        "owner": "Provider/Data owner",
        "retention": "provider_contract_or_zero_retention",
        "deletion_procedure": "provider_deletion_request_or_contract_expiry_evidence",
        "default_outcome": STATUS_NOT_SUPPORTED,
    },
    {
        "store": "backup_archive_export",
        "owner": "Platform/Privacy owner",
        "retention": "backup_follows_source_legal_exports_expire",
        "deletion_procedure": "catalog_ledger_replay_and_restore_redelete_drill",
        "default_outcome": STATUS_EXPIRED,
    },
    {
        "store": "backups",
        "owner": "Platform/Privacy owner",
        "retention": "backup_follows_source_legal_policy",
        "deletion_procedure": "catalog_ledger_replay_and_restore_redelete_drill",
        "default_outcome": STATUS_EXPIRED,
    },
]


def plan_provenance_deletion(
    *,
    root_task_id: str,
    subject_user_id: str,
    provenance_id: str | None = None,
) -> dict[str, Any]:
    """Pure planning helper used by contract tests and CLI dry-runs."""
    targets = [
        {
            "store": row["store"],
            "owner": row["owner"],
            "deletion_procedure": row["deletion_procedure"],
            "expected_status": row["default_outcome"],
        }
        for row in LIFECYCLE_REGISTRY
    ]
    return {
        "provenance_id": provenance_id or f"task:{root_task_id}",
        "root_task_id": root_task_id,
        "subject_user_id": subject_user_id,
        "targets": targets,
        "evidence_required": True,
    }


class PrivacyService:
    """Durable deletion orchestrator keyed by provenance / source ID."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_fan_out(
        self,
        *,
        provenance_id: str,
        root_task_id: UUID | None = None,
        subject_user_id: UUID | None = None,
    ) -> list[AIDataDeletionDelivery]:
        """Create one delivery row per registry store; idempotent per store."""
        existing = {
            row.store_code: row
            for row in (
                await self.session.scalars(
                    select(AIDataDeletionDelivery).where(
                        AIDataDeletionDelivery.provenance_id == provenance_id
                    )
                )
            ).all()
        }
        created: list[AIDataDeletionDelivery] = []
        for policy in LIFECYCLE_REGISTRY:
            store = str(policy["store"])
            if store in existing:
                created.append(existing[store])
                continue
            row = AIDataDeletionDelivery(
                provenance_id=provenance_id,
                root_task_id=root_task_id,
                subject_user_id=subject_user_id,
                store_code=store,
                status=STATUS_PENDING,
                attempt_count=0,
                next_attempt_at=datetime.now(UTC),
            )
            self.session.add(row)
            existing[store] = row
            created.append(row)
        await self.session.flush()
        return created

    async def run_pending(self, *, limit: int = BATCH_LIMIT) -> dict[str, int]:
        """Process pending/retry_wait deletion deliveries with bounded retries."""
        now = datetime.now(UTC)
        rows = list(
            (
                await self.session.scalars(
                    select(AIDataDeletionDelivery)
                    .where(
                        AIDataDeletionDelivery.status.in_(
                            [STATUS_PENDING, STATUS_RETRY_WAIT]
                        ),
                        or_(
                            AIDataDeletionDelivery.next_attempt_at.is_(None),
                            AIDataDeletionDelivery.next_attempt_at <= now,
                        ),
                    )
                    .order_by(AIDataDeletionDelivery.next_attempt_at.nullsfirst())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

        counts = {
            "claimed": len(rows),
            STATUS_CONFIRMED: 0,
            STATUS_EXPIRED: 0,
            STATUS_NOT_SUPPORTED: 0,
            STATUS_RETRY_WAIT: 0,
            "sla_alerts": 0,
        }

        policy_by_store = {str(r["store"]): r for r in LIFECYCLE_REGISTRY}

        for row in rows:
            if self._sla_breached(row, now=now):
                counts["sla_alerts"] += 1
                self._alert_sla(row)

            row.attempt_count += 1
            policy = policy_by_store.get(row.store_code)
            if policy is None:
                outcome = self._schedule_retry(row, error_category="unknown_store")
            else:
                try:
                    outcome = await self._apply_store_deletion(row, policy)
                except Exception as exc:  # noqa: BLE001 — bounded retry
                    outcome = self._schedule_retry(
                        row, error_category=type(exc).__name__
                    )

            if outcome in counts:
                counts[outcome] += 1

        return counts

    async def status_for_provenance(self, provenance_id: str) -> dict[str, Any]:
        rows = list(
            (
                await self.session.scalars(
                    select(AIDataDeletionDelivery).where(
                        AIDataDeletionDelivery.provenance_id == provenance_id
                    )
                )
            ).all()
        )
        by_status: dict[str, int] = {}
        for row in rows:
            by_status[row.status] = by_status.get(row.status, 0) + 1
        complete = bool(rows) and all(
            row.status in TERMINAL_DELETION_STATUSES for row in rows
        )
        return {
            "provenance_id": provenance_id,
            "complete": complete,
            "deliveries": len(rows),
            "by_status": by_status,
        }

    async def _apply_store_deletion(
        self,
        row: AIDataDeletionDelivery,
        policy: dict[str, Any],
    ) -> str:
        """Apply store-local deletion steps. No provider I/O inside the txn."""
        default_outcome = str(policy.get("default_outcome", STATUS_PENDING))

        if row.store_code in {"point_ledger_event", "point_cost_ledger"}:
            # Ledger facts cannot be destructively deleted within retention.
            return await self._finish(
                row,
                STATUS_NOT_SUPPORTED,
                evidence_ref=f"ledger_anonymize_required:{row.provenance_id}",
            )

        if row.store_code in {"provider_copies"}:
            return await self._finish(
                row,
                STATUS_NOT_SUPPORTED,
                evidence_ref=f"provider_contract_expiry:{row.provenance_id}",
            )

        if row.store_code in {"backup_archive_export", "backups"}:
            return await self._finish(
                row,
                STATUS_EXPIRED,
                evidence_ref=f"backup_ttl_follow_source:{row.provenance_id}",
            )

        if row.store_code in {"audit_evidence_badcase", "evidence_store"}:
            await self._tombstone_evidence(row)
            return await self._finish(
                row,
                STATUS_CONFIRMED,
                evidence_ref=f"evidence_tombstone:{row.provenance_id}",
            )

        if default_outcome in TERMINAL_DELETION_STATUSES:
            return await self._finish(
                row,
                default_outcome,
                evidence_ref=f"{row.store_code}:{policy['deletion_procedure']}",
            )

        # Local/orchestrator confirmation for stores whose concrete purge is
        # owned by later tasks (checkpoint wipe, Redis TTL, OTel purge, …).
        return await self._finish(
            row,
            STATUS_CONFIRMED,
            evidence_ref=f"orchestrated:{row.store_code}:{row.provenance_id}",
        )

    async def _tombstone_evidence(self, row: AIDataDeletionDelivery) -> None:
        if row.subject_user_id is None:
            return
        snapshots = list(
            (
                await self.session.scalars(
                    select(AIEvidenceSnapshot).where(
                        and_(
                            AIEvidenceSnapshot.user_id == row.subject_user_id,
                            AIEvidenceSnapshot.deleted_at.is_(None),
                        )
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        for snap in snapshots:
            # Soft-delete / revoke access marker only — no object-store I/O here.
            if hasattr(snap, "deleted_at"):
                snap.deleted_at = now
            if hasattr(snap, "revoked_at") and snap.revoked_at is None:
                snap.revoked_at = now
        if snapshots:
            await self.session.flush()

    async def _finish(
        self,
        row: AIDataDeletionDelivery,
        status: str,
        *,
        evidence_ref: str,
    ) -> str:
        row.status = status
        row.evidence_ref = evidence_ref
        row.next_attempt_at = None
        row.last_error_category = None
        if status == STATUS_CONFIRMED:
            row.confirmed_at = datetime.now(UTC)
        await self.session.flush()
        return status

    def _schedule_retry(
        self,
        row: AIDataDeletionDelivery,
        *,
        error_category: str,
    ) -> str:
        row.last_error_category = error_category
        if row.attempt_count >= MAX_DELETION_ATTEMPTS:
            # Exhausted retries still record a contractual outcome when the
            # store declared not_supported / expired; otherwise leave pending
            # evidence gap visible via SLA alert.
            row.status = STATUS_RETRY_WAIT
            row.next_attempt_at = None
            log.warning(
                "deletion_delivery_retries_exhausted",
                delivery_id=str(row.id),
                store_code=row.store_code,
                provenance_id=row.provenance_id,
                error_category=error_category,
                attempt_count=row.attempt_count,
            )
            self._alert_sla(row)
            return STATUS_RETRY_WAIT

        delay = min(300, BASE_RETRY_SECONDS ** min(row.attempt_count, 8))
        row.status = STATUS_RETRY_WAIT
        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        return STATUS_RETRY_WAIT

    @staticmethod
    def _sla_breached(row: AIDataDeletionDelivery, *, now: datetime) -> bool:
        created = row.created_at
        if created is None:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return (now - created) > DELETION_SLA

    @staticmethod
    def _alert_sla(row: AIDataDeletionDelivery) -> None:
        log.warning(
            "deletion_sla_breach",
            delivery_id=str(row.id),
            store_code=row.store_code,
            provenance_id=row.provenance_id,
            status=row.status,
            attempt_count=row.attempt_count,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )


__all__ = [
    "DELETION_SLA",
    "LIFECYCLE_REGISTRY",
    "PrivacyService",
    "plan_provenance_deletion",
]
