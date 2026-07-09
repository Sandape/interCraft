"""AbilityProfileService — business logic for dashboard, share, export, admin.

Per contracts/ and research.md R-5 (time-weighted averaging).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException

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
        # Read existing ability_dimensions via raw query (no RLS conflict)
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
                        "date": h["snapshot_date"].isoformat() if hasattr(h["snapshot_date"], "isoformat") else str(h["snapshot_date"]),
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
        """Aggregate ability_dimensions rows into one entry per dimension_key.

        The same dimension_key can have multiple rows (1 manual baseline + 1
        per interview, all is_active=true). We collapse them so the frontend
        always sees 6 dimensions with the right semantic split:
          - actual_score  = latest interview/coach score (system-derived)
          - self_assessed = latest manual/self score (user-set baseline)
          - source        = 'manual' when no system data exists
        """
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("""
                SELECT dimension_key, actual_score, ideal_score, source, is_active,
                       created_at
                FROM ability_dimensions
                WHERE user_id = :user_id AND is_active = true
                ORDER BY dimension_key, created_at DESC
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()

        # Group rows by dimension_key. With ORDER BY created_at DESC, the
        # first row per dim is the latest.
        by_dim: dict[str, list[dict]] = {}
        for r in rows:
            entry = {
                "dimension_key": r[0],
                "actual_score": r[1],
                "ideal_score": r[2],
                "source": r[3],
                "is_active": r[4],
                "created_at": r[5],
            }
            by_dim.setdefault(entry["dimension_key"], []).append(entry)

        aggregated: list[dict] = []
        for dim_key, entries in by_dim.items():
            system_entry = next(
                (e for e in entries if e["source"] in ("interview", "coach")),
                None,
            )
            manual_entry = next(
                (e for e in entries if e["source"] in ("manual", "self")),
                None,
            )

            if system_entry is not None:
                actual_score = float(system_entry["actual_score"] or 0)
                ideal_score = float(system_entry["ideal_score"] or 10)
                source = system_entry["source"]
            elif manual_entry is not None:
                actual_score = float(manual_entry["actual_score"] or 0)
                ideal_score = float(manual_entry["ideal_score"] or 10)
                source = manual_entry["source"]
            else:
                actual_score = 0.0
                ideal_score = 10.0
                source = "manual"

            self_assessed_score = (
                float(manual_entry["actual_score"] or 0)
                if manual_entry is not None
                else None
            )

            aggregated.append({
                "dimension_key": dim_key,
                "actual_score": actual_score,
                "ideal_score": ideal_score,
                "source": source,
                "is_active": True,
                "self_assessed_score": self_assessed_score,
            })
        return aggregated

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

    # ── Self-Assessment ──────────────────────────────────────────────────────

    async def self_assess(
        self, user_id: UUID, dimension_key: str, score: float, notes: str | None = None
    ) -> dict:
        """Self-assess a dimension. Uses the existing PATCH endpoint logic."""
        from app.modules.abilities.repository import AbilityDimensionRepository
        from app.modules.abilities.schemas import ALLOWED_DIMENSION_KEYS

        if dimension_key not in ALLOWED_DIMENSION_KEYS:
            raise HTTPException(status_code=422, detail=f"Invalid dimension_key: {dimension_key}")

        ability_repo = AbilityDimensionRepository(self.repo.session)
        patch_data = {"actual_score": Decimal(str(score)), "source": "manual"}
        instance = await ability_repo.patch(user_id, dimension_key, patch_data)
        if instance is None:
            raise HTTPException(status_code=404, detail="Dimension not found")
        if notes:
            # Store notes in sub_scores notes field
            sub_scores = dict(instance.sub_scores) if instance.sub_scores else {}
            sub_scores["notes"] = notes
            await ability_repo.patch(user_id, dimension_key, {"sub_scores": sub_scores})

        return {
            "dimension_key": instance.dimension_key,
            "actual_score": float(instance.actual_score),
            "source": instance.source,
        }

    # ── System Score Aggregation ─────────────────────────────────────────────

    async def aggregate_system_scores(self, user_id: UUID) -> dict[str, float]:
        """Compute time-weighted average per dimension for interview/coach sources.

        Uses linear decay per research.md R-5:
            weight_n = 1 + (n - 1) * 0.2
            weighted_avg = sum(score_n * weight_n) / sum(weight_n)
        """
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("""
                SELECT dimension_key, actual_score, created_at
                FROM ability_dimensions
                WHERE user_id = :user_id AND source IN ('interview', 'coach') AND is_active = true
                ORDER BY dimension_key, created_at
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()

        scores_by_dim: dict[str, list[float]] = {}
        for r in rows:
            key = r[0]
            if key not in scores_by_dim:
                scores_by_dim[key] = []
            scores_by_dim[key].append(float(r[1]))

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
        self, user_id: UUID, pin: str | None = None, expires_in_hours: int | None = None
    ) -> dict:
        """Create a new share link. Enforce max 10 active per user."""
        active_count = await self.repo.count_active_share_links(user_id)
        if active_count >= 10:
            raise HTTPException(
                status_code=429,
                detail="Active share links limit reached",
            )

        import bcrypt
        from app.core.ids import new_uuid_v7

        token = str(new_uuid_v7())
        pin_hash = None
        if pin:
            pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(hours=expires_in_hours)

        from app.modules.ability_profile.models import ProfileShareLink

        link = ProfileShareLink(
            user_id=user_id,
            token=token,
            pin_hash=pin_hash,
            expires_at=expires_at,
        )
        created = await self.repo.create_share_link(link)

        return {
            "id": created.id,
            "token": created.token,
            "url": f"/shared/{created.token}",
            "has_pin": created.pin_hash is not None,
            "expires_at": created.expires_at,
            "created_at": created.created_at,
        }

    async def revoke_share_link(self, user_id: UUID, link_id: UUID) -> None:
        link = await self.repo.revoke_share_link(link_id, user_id)
        if link is None:
            raise HTTPException(status_code=404, detail="Share link not found")
        logger.info("ability_profile.share_revoked", extra={"link_id": str(link_id), "user_id": str(user_id)})

    async def list_share_links(self, user_id: UUID) -> list[dict]:
        links = await self.repo.list_share_links(user_id)
        now = datetime.now(timezone.utc)
        results = []
        for l in links:
            if l.revoked_at:
                status = "revoked"
            elif l.expires_at and l.expires_at.replace(tzinfo=timezone.utc) < now:
                status = "expired"
            else:
                status = "active"
            results.append({
                "id": l.id,
                "token": l.token,
                "url": f"/shared/{l.token}",
                "has_pin": l.pin_hash is not None,
                "expires_at": l.expires_at,
                "revoked_at": l.revoked_at,
                "access_count": l.access_count,
                "last_accessed_at": l.last_accessed_at,
                "status": status,
                "created_at": l.created_at,
            })
        return results

    async def get_shared_profile(self, token: str, pin: str | None = None) -> dict:
        """Public access to shared profile. Verifies PIN if set."""
        import bcrypt
        from sqlalchemy import text

        link = await self.repo.get_share_link_by_token(token)
        if link is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        now = datetime.now(timezone.utc)

        # Check revoked
        if link.revoked_at:
            raise HTTPException(status_code=404, detail="Profile not found or access revoked")

        # Check expired
        if link.expires_at and link.expires_at.replace(tzinfo=timezone.utc) < now:
            raise HTTPException(status_code=404, detail="Profile not found or access revoked")

        # PIN verification
        if link.pin_hash:
            if not pin:
                raise HTTPException(status_code=401, detail="PIN required")
            if not bcrypt.checkpw(pin.encode(), link.pin_hash.encode()):
                raise HTTPException(status_code=401, detail="Invalid PIN")

        # Record access
        await self.repo.record_share_link_access(token)

        # Temporarily switch RLS context to the share link owner so we can read
        # their ability_dimensions / ability_dimensions_history.  SET LOCAL is
        # transaction-scoped and will be reset on session commit.
        await self.repo.session.execute(
            text("SELECT set_config('app.user_id', :u, true)"),
            {"u": str(link.user_id)},
        )

        # Get owner info
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

    # ── Export ───────────────────────────────────────────────────────────────

    async def trigger_export(self, user_id: UUID) -> dict:
        """Trigger PDF export. Enforce 5/h limit."""
        recent_count = await self.repo.count_exports_last_hour(user_id)
        if recent_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Export rate limit exceeded (5/hour)",
            )

        from app.modules.ability_profile.models import ExportLog

        log = ExportLog(user_id=user_id, status="pending")
        created = await self.repo.create_export_log(log)

        # Enqueue to ARQ worker
        from app.core.redis import enqueue_job
        try:
            await enqueue_job("pdf_export", export_id=str(created.id), user_id=str(user_id))
        except Exception:
            logger.warning("Failed to enqueue PDF export job", exc_info=True)

        return {
            "export_id": created.id,
            "status": created.status,
            "estimated_wait_seconds": 10,
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
            "download_url": f"/api/v1/ability-profile/exports/{log.id}/download" if log.status == "completed" else None,
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

    # ── Admin ────────────────────────────────────────────────────────────────

    async def get_admin_dashboard(self, admin_id: UUID, target_user_id: UUID) -> dict:
        """Admin view of a target user's dashboard."""
        # Verify admin role
        if not await self._is_admin(admin_id):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Verify target user exists
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("SELECT display_name FROM users WHERE id = :user_id AND deleted_at IS NULL"),
            {"user_id": target_user_id},
        )
        row = result.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_name = row[0] or "Unknown"

        dashboard = await self.get_dashboard(target_user_id)
        dashboard["viewed_user_id"] = target_user_id
        dashboard["viewed_user_name"] = user_name

        logger.info("ability_profile.admin_viewed", extra={
            "admin_id": str(admin_id), "target_user_id": str(target_user_id),
        })
        return dashboard

    async def _is_admin(self, user_id: UUID) -> bool:
        from sqlalchemy import text

        result = await self.repo.session.execute(
            text("SELECT is_admin FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )
        row = result.fetchone()
        return row is not None and bool(row[0])


__all__ = ["AbilityProfileService"]
