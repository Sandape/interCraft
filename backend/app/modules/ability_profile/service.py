"""AbilityProfileService — business logic for dashboard, share, export, admin.

Per contracts/ and research.md R-5 (time-weighted averaging).
PIN removed per Feature 024 US5. Sync PDF per Feature 024 US6.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.modules.ability_profile.repository import AbilityProfileRepository

logger = logging.getLogger(__name__)

# 6 dimensions with Chinese labels
DIMENSION_LABELS: dict[str, str] = {
    "tech_depth": "技术深度",
    "architecture": "架构能力",
    "engineering_practice": "工程实践",
    "communication": "沟通表达",
    "algorithm": "算法能力",
    "business": "业务理解",
}


class AbilityProfileService:
    def __init__(self, repo: AbilityProfileRepository, session=None) -> None:
        self.repo = repo
        self.session = session

    # ── Dashboard ────────────────────────────────────────────────────────────

    async def get_dashboard(self, user_id: UUID) -> dict:
        """Aggregate ability dimensions into dashboard response with trends."""
        dimensions = await self._fetch_ability_dimensions(user_id)
        history = await self._fetch_dimension_history(user_id)

        result_dims: list[dict] = []
        for dim in dimensions:
            key = dim["dimension_key"]
            dim_history = [h for h in history if h["dimension_key"] == key]
            trend = self._calculate_trend(dim_history)
            result_dims.append({
                "key": key,
                "label_zh": DIMENSION_LABELS.get(key, key),
                "actual_score": float(dim.get("actual_score", 0)),
                "ideal_score": float(dim.get("ideal_score", 10)),
                "self_assessed_score": dim.get("self_assessed_score"),
                "source": dim.get("source", "manual"),
                "trend": trend,
                "history": [
                    {
                        "date": h["snapshot_date"].isoformat()
                        if hasattr(h["snapshot_date"], "isoformat")
                        else str(h["snapshot_date"]),
                        "actual_score": float(h.get("actual_score", 0)),
                        "ideal_score": float(h.get("ideal_score", 10)),
                    }
                    for h in dim_history
                ],
            })

        return {
            "dimensions": result_dims,
            "generated_at": datetime.now(timezone.utc),
        }

    def _calculate_trend(self, history: list[dict]) -> str:
        if len(history) < 2:
            return "stable"
        sorted_h = sorted(history, key=lambda h: h["snapshot_date"])
        latest = float(sorted_h[-1]["actual_score"])
        prev = float(sorted_h[-2]["actual_score"])
        diff = latest - prev
        if diff > 0.5:
            return "up"
        if diff < -0.5:
            return "down"
        return "stable"

    async def _fetch_ability_dimensions(self, user_id: UUID) -> list[dict]:
        """Read ability_dimensions with dual-track self_assessed_score column.

        One row per (user_id, dimension_key). System score lives in actual_score
        (source=interview/coach after sync); user self-assessment lives in
        self_assessed_score and survives interview UPSERTs.
        """
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("""
                SELECT dimension_key, actual_score, ideal_score, source,
                       is_active, self_assessed_score
                FROM ability_dimensions
                WHERE user_id = :user_id AND is_active = true
                ORDER BY dimension_key
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()
        return [
            {
                "dimension_key": r[0],
                "actual_score": float(r[1] or 0),
                "ideal_score": float(r[2] or 10),
                "source": r[3] or "manual",
                "is_active": r[4],
                "self_assessed_score": float(r[5]) if r[5] is not None else None,
            }
            for r in rows
        ]

    async def _fetch_dimension_history(self, user_id: UUID) -> list[dict]:
        """Read ability_dimensions_history rows within current session."""
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("""
                SELECT dimension_key, snapshot_date, actual_score, ideal_score
                FROM ability_dimensions_history
                WHERE user_id = :user_id
                ORDER BY dimension_key, snapshot_date
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()
        return [
            {
                "dimension_key": r[0],
                "snapshot_date": r[1],
                "actual_score": r[2],
                "ideal_score": r[3],
            }
            for r in rows
        ]

    # ── Self-Assessment (delegates to abilities module) ──────────────────────

    async def self_assess(
        self, user_id: UUID, dimension_key: str, score: float, notes: str | None = None
    ) -> dict:
        """Self-assess a dimension into self_assessed_score (dual-track)."""
        from app.modules.abilities.repository import AbilityDimensionRepository
        from app.modules.abilities.schemas import ALLOWED_DIMENSION_KEYS

        if dimension_key not in ALLOWED_DIMENSION_KEYS:
            raise HTTPException(status_code=422, detail=f"Invalid dimension_key: {dimension_key}")

        ability_repo = AbilityDimensionRepository(self.repo.session)
        patch_data: dict = {
            "self_assessed_score": Decimal(str(score)),
        }
        instance = await ability_repo.patch(user_id, dimension_key, patch_data)
        if instance is None:
            raise HTTPException(status_code=404, detail="Dimension not found")
        if notes:
            sub_scores = dict(instance.sub_scores) if instance.sub_scores else {}
            sub_scores["_notes"] = notes
            await ability_repo.patch(user_id, dimension_key, {"sub_scores": sub_scores})
        await ability_repo.append_history_snapshot(
            user_id,
            dimension_key,
            actual_score=Decimal(str(score)),
            ideal_score=instance.ideal_score,
        )

        return {
            "dimension_key": instance.dimension_key,
            "self_assessed_score": float(instance.self_assessed_score or 0),
            "actual_score": float(instance.actual_score),
            "source": instance.source,
        }

    # ── System Score Aggregation (R-5; used when multi-row history exists) ───

    async def aggregate_system_scores(self, user_id: UUID) -> dict[str, float]:
        """Compute time-weighted average from history for interview/coach sources.

        Uses linear decay per research.md R-5:
            weight_n = 1 + (n - 1) * 0.2
            weighted_avg = sum(score_n * weight_n) / sum(weight_n)
        """
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("""
                SELECT dimension_key, actual_score, snapshot_date
                FROM ability_dimensions_history
                WHERE user_id = :user_id AND aggregate = 'day'
                ORDER BY dimension_key, snapshot_date
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()

        scores_by_dim: dict[str, list[float]] = {}
        for r in rows:
            scores_by_dim.setdefault(r[0], []).append(float(r[1]))

        result_dict: dict[str, float] = {}
        for dim_key, scores in scores_by_dim.items():
            n = len(scores)
            if n == 0:
                continue
            if n == 1:
                result_dict[dim_key] = scores[0]
                continue
            weights = [1.0 + i * 0.2 for i in range(n)]
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            weight_sum = sum(weights)
            result_dict[dim_key] = round(weighted_sum / weight_sum, 2)

        return result_dict

    # ── Share Links ──────────────────────────────────────────────────────────

    async def create_share_link(
        self, user_id: UUID, expires_in_hours: int | None = None
    ) -> dict:
        """Create a new share link. Enforce max 10 active per user. No PIN (024)."""
        active_count = await self.repo.count_active_share_links(user_id)
        if active_count >= 10:
            raise HTTPException(
                status_code=429,
                detail="Active share links limit reached",
            )

        from app.core.ids import new_uuid_v7
        from app.modules.ability_profile.models import ProfileShareLink

        token = str(new_uuid_v7())
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        link = ProfileShareLink(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        created = await self.repo.create_share_link(link)

        return {
            "id": created.id,
            "token": created.token,
            "url": f"/shared/{created.token}",
            "expires_at": created.expires_at,
            "created_at": created.created_at,
        }

    async def revoke_share_link(self, user_id: UUID, link_id: UUID) -> None:
        link = await self.repo.revoke_share_link(link_id, user_id)
        if link is None:
            raise HTTPException(status_code=404, detail="Share link not found")
        logger.info(
            "ability_profile.share_revoked",
            extra={"link_id": str(link_id), "user_id": str(user_id)},
        )

    async def list_share_links(self, user_id: UUID) -> list[dict]:
        links = await self.repo.list_share_links(user_id)
        now = datetime.now(timezone.utc)
        results = []
        for l in links:
            if l.revoked_at:
                status = "revoked"
            elif l.expires_at and _as_utc(l.expires_at) < now:
                status = "expired"
            else:
                status = "active"
            results.append({
                "id": l.id,
                "token": l.token,
                "url": f"/shared/{l.token}",
                "expires_at": l.expires_at,
                "revoked_at": l.revoked_at,
                "access_count": l.access_count,
                "last_accessed_at": l.last_accessed_at,
                "status": status,
                "created_at": l.created_at,
            })
        return results

    async def get_shared_profile(self, token: str) -> dict:
        """Public access to shared profile (no PIN — Feature 024)."""
        from sqlalchemy import text

        link = await self.repo.get_share_link_by_token(token)
        if link is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        now = datetime.now(timezone.utc)

        if link.revoked_at:
            # FR-043: revoked → 403
            raise HTTPException(status_code=403, detail="Share link has been revoked")

        if link.expires_at and _as_utc(link.expires_at) < now:
            # FR-043: expired → 410
            raise HTTPException(status_code=410, detail="Share link has expired")

        await self.repo.record_share_link_access(token)

        # Temporarily switch RLS context to the share link owner
        await self.repo.session.execute(
            text("SELECT set_config('app.user_id', :u, true)"),
            {"u": str(link.user_id)},
        )

        owner = await self._fetch_user_info(link.user_id)
        dashboard = await self.get_dashboard(link.user_id)

        return {
            "owner": {
                "name": owner.get("name", "Unknown"),
                "title": owner.get("title", None),
            },
            "generated_at": dashboard["generated_at"],
            "dimensions": [
                {
                    "key": d["key"],
                    "label_zh": d["label_zh"],
                    "actual_score": d["actual_score"],
                    "ideal_score": d["ideal_score"],
                }
                for d in dashboard["dimensions"]
            ],
        }

    async def _fetch_user_info(self, user_id: UUID) -> dict:
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("SELECT display_name, title FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )
        row = result.fetchone()
        if row:
            return {"name": row[0] or "", "title": row[1] or ""}
        return {"name": "Unknown", "title": None}

    # ── Export (024 sync primary path) ───────────────────────────────────────

    async def export_pdf_sync(self, user_id: UUID) -> FileResponse:
        """Generate PDF synchronously and return FileResponse (024 FR-050)."""
        from app.modules.ability_profile.pdf import generate_profile_pdf

        filepath = await generate_profile_pdf(user_id)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"ability-profile-{user_id}-{date_str}.pdf"
        return FileResponse(
            path=filepath,
            media_type="application/pdf",
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    async def trigger_export(self, user_id: UUID) -> dict:
        """Legacy async export trigger — kept for backward compat, generates sync.

        Prefer GET /export-pdf. This path still writes an ExportLog for audit
        but generates the PDF inline (no ARQ).
        """
        recent_count = await self.repo.count_exports_last_hour(user_id)
        if recent_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Export rate limit exceeded (5/hour)",
            )

        from app.modules.ability_profile.models import ExportLog
        from app.modules.ability_profile.pdf import generate_profile_pdf

        log = ExportLog(user_id=user_id, status="processing")
        created = await self.repo.create_export_log(log)

        try:
            filepath = await generate_profile_pdf(user_id)
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else None
            await self.repo.update_export_status(
                created.id,
                "completed",
                file_path=filepath,
                file_size_bytes=file_size,
                completed_at=datetime.now(timezone.utc),
            )
            status = "completed"
        except Exception as e:
            await self.repo.update_export_status(
                created.id,
                "failed",
                error_message=str(e)[:500],
                completed_at=datetime.now(timezone.utc),
            )
            raise HTTPException(status_code=500, detail="PDF generation failed") from e

        return {
            "export_id": created.id,
            "status": status,
            "estimated_wait_seconds": 0,
            "requested_at": created.requested_at,
        }

    async def get_export_status(self, user_id: UUID, export_id: UUID) -> dict:
        log = await self.repo.get_export_log(export_id, user_id)
        if log is None:
            raise HTTPException(status_code=404, detail="Export not found")
        return {
            "export_id": log.id,
            "status": log.status,
            "file_size_bytes": log.file_size_bytes,
            "file_path": log.file_path,
            "download_url": (
                f"/api/v1/ability-profile/exports/{log.id}/download"
                if log.status == "completed"
                else None
            ),
            "requested_at": log.requested_at,
            "completed_at": log.completed_at,
        }

    async def list_exports(self, user_id: UUID, limit: int = 10) -> list[dict]:
        logs = await self.repo.list_export_logs(user_id, limit=limit)
        return [
            {
                "export_id": l.id,
                "status": l.status,
                "file_size_bytes": l.file_size_bytes,
                "requested_at": l.requested_at,
                "completed_at": l.completed_at,
            }
            for l in logs
        ]

    async def download_export_file(self, user_id: UUID, export_id: UUID) -> FileResponse:
        """Download a previously generated export using file_path (not URL)."""
        log = await self.repo.get_export_log(export_id, user_id)
        if log is None:
            raise HTTPException(status_code=404, detail="Export not found")
        if log.status != "completed" or not log.file_path:
            raise HTTPException(status_code=400, detail="Export not yet completed")
        if not os.path.exists(log.file_path):
            raise HTTPException(status_code=404, detail="Export file missing")
        return FileResponse(
            path=log.file_path,
            media_type="application/pdf",
            filename="ability-profile.pdf",
        )

    # ── Admin ────────────────────────────────────────────────────────────────

    async def get_admin_dashboard(self, admin_id: UUID, target_user_id: UUID) -> dict:
        """Admin view of a target user's dashboard."""
        if not await self._is_admin(admin_id):
            raise HTTPException(status_code=403, detail="Admin access required")

        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("SELECT display_name FROM users WHERE id = :user_id AND deleted_at IS NULL"),
            {"user_id": target_user_id},
        )
        row = result.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_name = row[0] or "Unknown"

        # Switch RLS to target user for dimension reads
        await self.repo.session.execute(
            text("SELECT set_config('app.user_id', :u, true)"),
            {"u": str(target_user_id)},
        )

        dashboard = await self.get_dashboard(target_user_id)
        dashboard["viewed_user_id"] = target_user_id
        dashboard["viewed_user_name"] = user_name

        logger.info(
            "ability_profile.admin_viewed",
            extra={"admin_id": str(admin_id), "target_user_id": str(target_user_id)},
        )
        return dashboard

    async def _is_admin(self, user_id: UUID) -> bool:
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("SELECT is_admin FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )
        row = result.fetchone()
        return row is not None and bool(row[0])


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


__all__ = ["AbilityProfileService", "DIMENSION_LABELS"]
