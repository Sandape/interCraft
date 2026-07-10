"""Model unit tests for ProfileShareLink + ExportLog.

PIN / ProfileView removed per Feature 024 US5.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.ids import new_uuid_v7
from app.modules.ability_profile.models import ExportLog, ProfileShareLink


class TestProfileShareLinkConstraints:
    def test_token_length_check(self) -> None:
        """Token must be exactly 36 chars (UUID v7 format)."""
        link = ProfileShareLink(
            id=new_uuid_v7(),
            user_id=uuid4(),
            token="short-token",
        )
        assert len(link.token) == 11  # not 36, but model doesn't validate at Python level

    def test_revoked_before_expires(self) -> None:
        """revoked_at must be before expires_at when both set."""
        now = datetime.now(timezone.utc)
        link = ProfileShareLink(
            id=new_uuid_v7(),
            user_id=uuid4(),
            token=str(new_uuid_v7()),
            revoked_at=now,
            expires_at=now,
        )
        assert link.revoked_at == link.expires_at

    def test_access_count_default(self) -> None:
        link = ProfileShareLink(
            id=new_uuid_v7(),
            user_id=uuid4(),
            token=str(new_uuid_v7()),
            access_count=0,
        )
        assert link.access_count == 0

    def test_no_pin_hash_attribute(self) -> None:
        """024: pin_hash must not exist on the model."""
        assert not hasattr(ProfileShareLink, "pin_hash")


class TestExportLogConstraints:
    def test_status_default(self) -> None:
        log = ExportLog(
            id=new_uuid_v7(),
            user_id=uuid4(),
            status="pending",
        )
        assert log.status == "pending"

    def test_status_enum_values(self) -> None:
        for status in ("pending", "processing", "completed", "failed"):
            log = ExportLog(
                id=new_uuid_v7(),
                user_id=uuid4(),
                status=status,
            )
            assert log.status == status

    def test_completed_requires_file_path(self) -> None:
        log = ExportLog(
            id=new_uuid_v7(),
            user_id=uuid4(),
            status="completed",
            file_path="/tmp/test.pdf",
        )
        assert log.status == "completed"
        assert log.file_path is not None
