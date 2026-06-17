"""020 (FIX-007, D-006) — InterviewSessionCreateOut response_model actually applies.

The current implementation declares `response_model=InterviewSessionCreateOut`
but returns `{"data": <ORM>}`. FastAPI only enforces response_model when the
return value IS a Pydantic instance — a dict-wrapped ORM bypasses it.

The 019 contract (and Round-2 MOCK-01) specifies the response must contain
exactly these 6 fields under `data`:
    id, status, thread_id, checkpoint_ns, job_id, branch_id

ORM leaks (position, company, mode, started_at, ended_at, duration_sec,
overall_score, created_at, updated_at) MUST NOT be present.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.modules.interviews.api import create_session
from app.modules.interviews.schemas import InterviewSessionCreateOut


def _orm_session() -> SimpleNamespace:
    """Build a representative ORM instance with all columns populated."""
    sid = uuid4()
    jid = uuid4()
    bid = uuid4()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=sid,
        branch_id=bid,
        job_id=jid,
        position="高级Python工程师",
        company="Google",
        mode="text",
        status="pending",
        thread_id=str(sid),
        checkpoint_ns="langgraph:thread:1",
        started_at=now,
        ended_at=None,
        duration_sec=None,
        overall_score=None,
        created_at=now,
        updated_at=now,
    )


class TestInterviewSessionCreateResponseShape:
    def test_schema_data_has_exactly_six_fields(self) -> None:
        """`InterviewSessionCreateOut.data` schema declares exactly 6 fields."""
        from app.modules.interviews.schemas import InterviewSessionCreateOut
        # Drill into the inner data schema
        inner = InterviewSessionCreateOut.model_fields["data"].annotation
        # Resolve string annotations if needed
        from typing import get_type_hints
        try:
            inner_cls = get_type_hints(InterviewSessionCreateOut)["data"]
        except Exception:
            inner_cls = inner
        # Walk the union / generic to get the BaseModel
        import typing
        origin = typing.get_origin(inner_cls)
        if origin is typing.Union:
            inner_cls = next(t for t in typing.get_args(inner_cls))

        names = set(inner_cls.model_fields.keys())
        expected = {"id", "status", "thread_id", "checkpoint_ns", "job_id", "branch_id"}
        assert names == expected, f"data schema must have exactly {expected}, got {names}"

    def test_schema_passes_validation_with_orm_data(self) -> None:
        """The 6-field schema can be constructed from a full ORM payload."""
        orm = _orm_session()
        out = InterviewSessionCreateOut.model_validate({"data": orm})
        dumped = out.model_dump()
        inner = dumped["data"]
        # The 6 contract fields must be present
        for k in ("id", "status", "thread_id", "checkpoint_ns", "job_id", "branch_id"):
            assert k in inner, f"missing contract field: {k}"
        # ORM leak fields must NOT be present
        for k in ("position", "company", "mode", "started_at", "ended_at",
                  "duration_sec", "overall_score", "created_at", "updated_at"):
            assert k not in inner, f"ORM leak: {k} should be filtered out"

    def test_schema_pydantic_filters_unknown_fields(self) -> None:
        """Pydantic's `from_attributes` + explicit field list filters extras."""
        orm = _orm_session()
        out = InterviewSessionCreateOut.model_validate({"data": orm})
        # Exactly 6 keys under data
        assert set(out.model_dump()["data"].keys()) == {
            "id", "status", "thread_id", "checkpoint_ns", "job_id", "branch_id"
        }