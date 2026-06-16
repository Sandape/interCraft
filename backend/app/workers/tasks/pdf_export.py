"""ARQ worker task: pdf_export — generates PDF for ability profile exports."""
from __future__ import annotations

import logging
import os
from uuid import UUID

from app.core.db import get_session_factory

logger = logging.getLogger("workers.pdf_export")


async def pdf_export(ctx: dict, export_id: str, user_id: str) -> dict:
    """Generate PDF export for a user's ability profile."""
    logger.info("pdf_export.start", export_id=export_id, user_id=user_id)

    factory = get_session_factory()
    async with factory() as session:
        from app.modules.ability_profile.repository import AbilityProfileRepository
        from app.modules.ability_profile.pdf import generate_profile_pdf

        repo = AbilityProfileRepository(session)

        # Update status to processing
        log = await repo.update_export_status(UUID(export_id), "processing")
        if log is None:
            logger.error("pdf_export.log_not_found", export_id=export_id)
            return {"status": "failed", "error": "Export log not found"}

        try:
            filepath = await generate_profile_pdf(UUID(user_id))
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

            await repo.update_export_status(
                UUID(export_id),
                "completed",
                file_path=filepath,
                file_size_bytes=file_size,
                completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            logger.info("pdf_export.completed", export_id=export_id, path=filepath, size=file_size)
            return {"status": "completed", "path": filepath, "size": file_size}

        except Exception as e:
            logger.error("pdf_export.failed", export_id=export_id, error=str(e))
            await repo.update_export_status(
                UUID(export_id),
                "failed",
                error_message=str(e),
                completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            return {"status": "failed", "error": str(e)}


__all__ = ["pdf_export"]
