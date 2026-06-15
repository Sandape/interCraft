"""Phase 6 — Export service (M21): ZIP packaging with JSON + Markdown."""
from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.account.models import ExportTask
from app.modules.account.notification import NotificationService


class ExportError(Exception):
    pass


class ExportService:
    """Async data export: create task, package ZIP, track progress."""

    EXPORTABLE_TYPES = ["resumes", "interviews", "error_questions", "ability_dimensions", "activities"]

    def __init__(self, db: AsyncSession, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()

    async def create_export_task(self, include: list[str] | None = None) -> ExportTask:
        if include is None:
            include = self.EXPORTABLE_TYPES
        # Validate types
        for t in include:
            if t not in self.EXPORTABLE_TYPES:
                raise ExportError(f"不支持的导出类型: {t}")

        task = ExportTask(
            user_id=self.user_id,
            status="pending",
            include_types=include,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_task(self, task_id: UUID) -> ExportTask | None:
        result = await self.db.execute(
            select(ExportTask).where(
                ExportTask.id == task_id,
                ExportTask.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def process_export(self, task: ExportTask) -> None:
        """Process an export task: collect data, build ZIP, store file."""
        task.status = "processing"
        await self.db.flush()

        try:
            export_dir = Path(self.settings.export_storage_path) / str(self.user_id)
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = export_dir / f"export_{timestamp}.zip"

            types_include = task.include_types or self.EXPORTABLE_TYPES

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, data_type in enumerate(types_include):
                    data = await self._collect_data(data_type)
                    json_bytes = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
                    zf.writestr(f"{data_type}/data.json", json_bytes)

                    if data_type == "resumes":
                        for branch in data.get("branches", []):
                            md_content = branch.get("content_md", "")
                            if md_content:
                                safe_name = "".join(c for c in branch.get("name", "resume") if c.isalnum() or c in " _-")
                                zf.writestr(f"resumes/{safe_name}.md", md_content)

                    task.progress_pct = int(((idx + 1) / len(types_include)) * 100)
                    await self.db.flush()

            file_size = zip_path.stat().st_size
            expires_at = datetime.now(timezone.utc) + timedelta(hours=self.settings.export_expiry_hours)

            task.status = "completed"
            task.file_path = str(zip_path)
            task.file_size_bytes = file_size
            task.progress_pct = 100
            task.completed_at = datetime.now(timezone.utc)
            task.expires_at = expires_at
            await self.db.flush()

            notif = NotificationService(self.db, self.user_id)
            await notif.create(
                type_="export_ready",
                title="数据导出已完成",
                message="您的数据导出已准备就绪，请在 72 小时内下载。",
                related_task_id=task.id,
            )

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            await self.db.flush()
            raise

    async def _collect_data(self, data_type: str) -> dict:
        """Collect data for a specific type. Returns serializable dict."""
        from sqlalchemy import text as sa_text

        tables = {
            "resumes": ("resume_branches", "resume_blocks"),
            "interviews": ("interview_sessions", "interview_reports"),
            "error_questions": "error_questions",
            "ability_dimensions": "ability_dimensions",
            "activities": "activities",
        }
        table_name = tables.get(data_type)
        if table_name is None:
            return {}

        if isinstance(table_name, tuple):
            result = {}
            for t in table_name:
                rows = await self.db.execute(
                    sa_text(f"SELECT * FROM {t} WHERE user_id = :uid ORDER BY created_at DESC").bindparams(uid=self.user_id)
                )
                result[t] = [dict(row._mapping) for row in rows]
            return result
        else:
            rows = await self.db.execute(
                sa_text(f"SELECT * FROM {table_name} WHERE user_id = :uid ORDER BY created_at DESC").bindparams(uid=self.user_id)
            )
            return {"items": [dict(row._mapping) for row in rows]}

    async def cleanup_expired_exports(self) -> dict:
        """Hourly cron: delete expired export files and records."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ExportTask).where(
                ExportTask.expires_at <= now,
                ExportTask.status == "completed",
            )
        )
        expired = result.scalars().all()
        deleted_count = 0
        for task in expired:
            if task.file_path and os.path.exists(task.file_path):
                os.remove(task.file_path)
            await self.db.delete(task)
            deleted_count += 1
        return {"deleted_count": deleted_count}
