"""Versioning service: create manual versions, rollback, restore."""
from __future__ import annotations

import copy
import difflib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import resume_versions_total
from app.modules.resumes.block_repository import ResumeBlockRepository
from app.modules.resumes.models import ResumeBlock, ResumeBranch
from app.modules.resumes.repository import ResumeRepository
from app.modules.versions.models import ResumeVersion
from app.modules.versions.repository import ResumeVersionRepository
from app.modules.versions.schemas import (
    BlockDiff,
    BlockLineDiff,
    BranchDiff,
    SnapshotBlock,
    VersionDiff,
)
from app.modules.versions.snapshot import build_snapshot, restore_version


class VersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResumeVersionRepository(session)
        self.resumes = ResumeRepository(session)
        self.blocks = ResumeBlockRepository(session)

    async def list_versions(
        self, branch_id: UUID, user_id: UUID, *, limit: int = 50
    ) -> list[ResumeVersion]:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return []
        return await self.repo.list_for_branch(branch_id, limit=limit)

    async def get_version(
        self, branch_id: UUID, version_no: int, user_id: UUID
    ) -> ResumeVersion | None:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        return await self.repo.get_by_no(branch_id, version_no)

    async def create_initial_version(
        self,
        *,
        branch_id: UUID,
        user_id: UUID,
        snapshot: dict,
    ) -> ResumeVersion:
        version_no = await self.repo.next_version_no(branch_id)
        v = await self.repo.create_full_snapshot(
            user_id=user_id,
            branch_id=branch_id,
            version_no=version_no,
            snapshot=snapshot,
            label="初始化",
            trigger="manual",
            author_type="user",
            actor_id=user_id,
        )
        resume_versions_total.labels(trigger="manual").inc()
        return v

    async def create_manual_version(
        self,
        *,
        branch_id: UUID,
        user_id: UUID,
        label: str | None = None,
    ) -> ResumeVersion | None:
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        blocks = await self.blocks.list_for_branch(branch_id)
        snapshot = build_snapshot(branch, blocks)
        version_no = await self.repo.next_version_no(branch_id)
        v = await self.repo.create_full_snapshot(
            user_id=user_id,
            branch_id=branch_id,
            version_no=version_no,
            snapshot=snapshot,
            label=label,
            trigger="manual",
            author_type="user",
            actor_id=user_id,
        )
        resume_versions_total.labels(trigger="manual").inc()
        return v

    async def get_snapshot(
        self, branch_id: UUID, version_no: int, user_id: UUID
    ) -> dict | None:
        v = await self.get_version(branch_id, version_no, user_id)
        if v is None:
            return None
        return await restore_version(self.session, v.id)

    async def rollback_to_version(
        self,
        *,
        branch_id: UUID,
        version_no: int,
        user_id: UUID,
        new_name: str | None = None,
    ) -> ResumeBranch | None:
        target = await self.get_version(branch_id, version_no, user_id)
        if target is None:
            return None
        snapshot = await restore_version(self.session, target.id)
        original = await self.resumes.get(branch_id, user_id=user_id)
        if original is None:
            return None
        if new_name is None:
            new_name = f"回滚自 {original.name} @ v{version_no}"
        new_branch = ResumeBranch(
            user_id=user_id,
            parent_id=original.id,
            name=new_name,
            company=original.company,
            position=original.position,
            status=original.status,
        )
        self.session.add(new_branch)
        await self.session.flush()
        await self.session.refresh(new_branch)

        for sb in snapshot.get("blocks", []):
            self.session.add(
                ResumeBlock(
                    user_id=user_id,
                    branch_id=new_branch.id,
                    type=sb.get("type", "custom"),
                    title=sb.get("title"),
                    content_md=sb.get("content_md", ""),
                    meta=copy.deepcopy(sb.get("meta")) if sb.get("meta") else None,
                    order_index=sb.get("order_index", "a0"),
                )
            )
        await self.session.flush()

        # Initial version on the new branch
        new_blocks = await self.blocks.list_for_branch(new_branch.id)
        snap = build_snapshot(new_branch, new_blocks)
        await self.create_initial_version(
            branch_id=new_branch.id,
            user_id=user_id,
            snapshot=snap,
        )
        # Patch the label slightly
        from sqlalchemy import update

        stmt = (
            update(ResumeVersion)
            .where(
                ResumeVersion.branch_id == new_branch.id,
                ResumeVersion.label == "初始化",
            )
            .values(label=f"回滚自 v{version_no}")
        )
        await self.session.execute(stmt)
        return new_branch

    # ---- Version diff (spec 027 US7 FR-049/050) ----

    async def diff_versions(
        self,
        *,
        branch_id: UUID,
        v1_no: int,
        v2_no: int,
        user_id: UUID,
    ) -> VersionDiff | None:
        """Compute a structured diff between two versions of the same branch.

        Returns None when either version is missing or the branch doesn't
        belong to the user. Returns a VersionDiff otherwise.
        """
        branch = await self.resumes.get(branch_id, user_id=user_id)
        if branch is None:
            return None
        v1 = await self.repo.get_by_no(branch_id, v1_no)
        v2 = await self.repo.get_by_no(branch_id, v2_no)
        if v1 is None or v2 is None:
            return None
        snap1 = await restore_version(self.session, v1.id)
        snap2 = await restore_version(self.session, v2.id)

        # Branch-level diff (name/company/position/status)
        b1 = snap1.get("branch", {})
        b2 = snap2.get("branch", {})
        branch_diff = BranchDiff(
            name=_pair_diff(b1.get("name"), b2.get("name")),
            company=_pair_diff(b1.get("company"), b2.get("company")),
            position=_pair_diff(b1.get("position"), b2.get("position")),
            status=_pair_diff(b1.get("status"), b2.get("status")),
        )

        # Block-level diff (LCS on (type|title) key)
        old_blocks = [SnapshotBlock.model_validate(b) for b in snap1.get("blocks", [])]
        new_blocks = [SnapshotBlock.model_validate(b) for b in snap2.get("blocks", [])]
        block_diffs = diff_blocks(old_blocks, new_blocks)

        summary = {
            "added": sum(1 for b in block_diffs if b.op == "added"),
            "removed": sum(1 for b in block_diffs if b.op == "removed"),
            "modified": sum(1 for b in block_diffs if b.op == "modified"),
            "unchanged": sum(1 for b in block_diffs if b.op == "unchanged"),
        }
        return VersionDiff(
            branch_id=str(branch_id),
            old_version_no=v1_no,
            new_version_no=v2_no,
            branch_diff=branch_diff,
            blocks=block_diffs,
            summary=summary,
        )


__all__ = ["VersionService"]


def _pair_diff(old: object, new: object) -> str | None:
    """Return a short summary string when two scalar values differ; None when equal.

    The frontend uses a non-null value to highlight the diff row; the
    string content is informational only. Format: 'old -> new'.
    """
    if old == new:
        return None
    return f"{old} -> {new}"


def _block_key(b: SnapshotBlock) -> str:
    """LCS key: (type|title). Title fallback to block id for uniqueness."""
    return f"{b.type}|{b.title or b.id}"


def _line_diff(a: str, b: str) -> list[BlockLineDiff]:
    """Line-level diff between two markdown strings using difflib.

    Splits on '\n', runs SequenceMatcher.get_opcodes, and emits
    per-line entries with kind ∈ {unchanged, added, removed}.
    """
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    sm = difflib.SequenceMatcher(a=a_lines, b=b_lines, autojunk=False)
    out: list[BlockLineDiff] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for line in a_lines[i1:i2]:
                out.append(BlockLineDiff(kind="unchanged", text=line))
        elif tag == "delete":
            for line in a_lines[i1:i2]:
                out.append(BlockLineDiff(kind="removed", text=line))
        elif tag == "insert":
            for line in b_lines[j1:j2]:
                out.append(BlockLineDiff(kind="added", text=line))
        elif tag == "replace":
            for line in a_lines[i1:i2]:
                out.append(BlockLineDiff(kind="removed", text=line))
            for line in b_lines[j1:j2]:
                out.append(BlockLineDiff(kind="added", text=line))
    return out


def diff_blocks(
    old_blocks: list[SnapshotBlock],
    new_blocks: list[SnapshotBlock],
) -> list[BlockDiff]:
    """Diff two ordered block lists using LCS on (type|title) key.

    Classification:
      - unchanged: same key + identical content_md
      - modified:  same key + different content_md
      - added:     present in new_blocks only
      - removed:   present in old_blocks only
    """
    old_keys = [_block_key(b) for b in old_blocks]
    new_keys = [_block_key(b) for b in new_blocks]
    sm = difflib.SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)
    out: list[BlockDiff] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for old, new in zip(old_blocks[i1:i2], new_blocks[j1:j2]):
                if old.content_md == new.content_md:
                    out.append(
                        BlockDiff(
                            op="unchanged",
                            key=_block_key(old),
                            type=old.type,
                            title=old.title,
                            old_block=old,
                            new_block=new,
                            line_diff=None,
                        )
                    )
                else:
                    out.append(
                        BlockDiff(
                            op="modified",
                            key=_block_key(old),
                            type=new.type,
                            title=new.title,
                            old_block=old,
                            new_block=new,
                            line_diff=_line_diff(old.content_md, new.content_md),
                        )
                    )
        elif tag == "delete":
            for old in old_blocks[i1:i2]:
                out.append(
                    BlockDiff(
                        op="removed",
                        key=_block_key(old),
                        type=old.type,
                        title=old.title,
                        old_block=old,
                        new_block=None,
                        line_diff=None,
                    )
                )
        elif tag == "insert":
            for new in new_blocks[j1:j2]:
                out.append(
                    BlockDiff(
                        op="added",
                        key=_block_key(new),
                        type=new.type,
                        title=new.title,
                        old_block=None,
                        new_block=new,
                        line_diff=None,
                    )
                )
        elif tag == "replace":
            for old in old_blocks[i1:i2]:
                out.append(
                    BlockDiff(
                        op="removed",
                        key=_block_key(old),
                        type=old.type,
                        title=old.title,
                        old_block=old,
                        new_block=None,
                        line_diff=None,
                    )
                )
            for new in new_blocks[j1:j2]:
                out.append(
                    BlockDiff(
                        op="added",
                        key=_block_key(new),
                        type=new.type,
                        title=new.title,
                        old_block=None,
                        new_block=new,
                        line_diff=None,
                    )
                )
    return out


__all__ = ["VersionService"]
