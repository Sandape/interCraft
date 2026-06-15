"""Phase 6 — Import service (M21): JSON + Markdown resume import."""
from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes.models import ResumeBranch, ResumeBlock
from app.modules.resumes.repository import ResumeRepository


class ImportError(Exception):
    pass


class ImportService:
    """Import resumes from JSON (export-symmetrical) or Markdown."""

    def __init__(self, db: AsyncSession, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id
        self.repo = ResumeRepository(db)

    async def import_json(self, content: str, branch_name: str | None = None) -> dict:
        """Import from JSON format (symmetrical with export)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ImportError(f"JSON 解析失败: {e}")

        branches_data = data.get("branches", data if isinstance(data, list) else [data])
        if not branches_data:
            raise ImportError("未找到有效的简历数据")

        first = branches_data[0] if isinstance(branches_data, list) else branches_data
        name = branch_name or first.get("name", f"导入简历 - {UUID(int=0)}")
        branch = ResumeBranch(
            user_id=self.user_id,
            name=name,
            company=first.get("company"),
            position=first.get("position"),
            is_main=False,
        )
        self.db.add(branch)
        await self.db.flush()

        blocks_data = first.get("blocks", [])
        blocks_count = 0
        for i, blk in enumerate(blocks_data):
            block = ResumeBlock(
                branch_id=branch.id,
                type=blk.get("type", "experience"),
                title=blk.get("title"),
                content_md=blk.get("content_md", ""),
                order_index=f"a{i:08}",
            )
            self.db.add(block)
            blocks_count += 1

        await self.db.flush()
        return {"branch_id": branch.id, "branch_name": name, "blocks_count": blocks_count}

    async def import_markdown(self, content: str, branch_name: str | None = None) -> dict:
        """Import from Markdown — parse headings as block titles."""
        name = branch_name or "导入简历"
        branch = ResumeBranch(
            user_id=self.user_id,
            name=name,
            is_main=False,
        )
        self.db.add(branch)
        await self.db.flush()

        # Parse Markdown: headings become block titles, content between headings becomes content_md
        lines = content.split("\n")
        blocks = []
        current_title = None
        current_content: list[str] = []

        heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            m = heading_re.match(line)
            if m:
                if current_title is not None or current_content:
                    blocks.append({"title": current_title, "content_md": "\n".join(current_content).strip()})
                current_title = m.group(2)
                current_content = []
            else:
                current_content.append(line)

        # Last block
        if current_title is not None or current_content:
            blocks.append({"title": current_title, "content_md": "\n".join(current_content).strip()})

        # If no headings found, treat entire content as one block
        if not blocks:
            blocks = [{"title": None, "content_md": content.strip()}]

        blocks_count = 0
        for i, blk in enumerate(blocks):
            block = ResumeBlock(
                branch_id=branch.id,
                type="experience",
                title=blk["title"],
                content_md=blk["content_md"],
                order_index=f"a{i:08}",
            )
            self.db.add(block)
            blocks_count += 1

        await self.db.flush()
        return {"branch_id": branch.id, "branch_name": name, "blocks_count": blocks_count}
