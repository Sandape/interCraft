"""Job fuzzy matching per FR-007 (REQ-054)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from uuid import UUID


@dataclass
class MatchResult:
    """Outcome of fuzzy job matching."""

    matched: Any | None = None
    candidates: list[Any] | None = None
    need_clarify: bool = False
    too_many: bool = False

    @property
    def unique(self) -> bool:
        return self.matched is not None and not self.need_clarify


def _attr(job: Any, name: str, default: Any = None) -> Any:
    if isinstance(job, dict):
        return job.get(name, default)
    return getattr(job, name, default)


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def match_jobs(
    jobs: Sequence[Any],
    *,
    company: str | None = None,
    position: str | None = None,
    job_id: UUID | str | None = None,
    max_candidates: int = 5,
) -> MatchResult:
    """Fuzzy-match a job from the user's active list.

    Priority (FR-007):
      (a) company + position exact
      (b) company contains
      (c) position contains
      (d) most recently updated
    """
    active = [j for j in jobs if _attr(j, "deleted_at") is None]
    if not active:
        return MatchResult(need_clarify=True, candidates=[])

    if job_id is not None:
        sid = str(job_id)
        for j in active:
            if str(_attr(j, "id")) == sid:
                return MatchResult(matched=j)
        return MatchResult(need_clarify=True, candidates=[])

    company_n = _norm(company)
    position_n = _norm(position)

    if not company_n and not position_n:
        # No hint — if only one job, use it; else ask
        if len(active) == 1:
            return MatchResult(matched=active[0])
        ranked = _sort_recent(active)
        if len(ranked) > max_candidates:
            return MatchResult(
                candidates=ranked[:max_candidates],
                need_clarify=True,
                too_many=True,
            )
        return MatchResult(candidates=ranked, need_clarify=True)

    # (a) exact company + position
    if company_n and position_n:
        exact = [
            j
            for j in active
            if _norm(_attr(j, "company")) == company_n
            and _norm(_attr(j, "position")) == position_n
        ]
        if len(exact) == 1:
            return MatchResult(matched=exact[0])
        if len(exact) > 1:
            return _clarify(exact, max_candidates)

    # (b) company contains / contained
    if company_n:
        by_company = [
            j
            for j in active
            if company_n in _norm(_attr(j, "company"))
            or _norm(_attr(j, "company")) in company_n
        ]
        if position_n:
            refined = [
                j
                for j in by_company
                if position_n in _norm(_attr(j, "position"))
                or _norm(_attr(j, "position")) in position_n
            ]
            if refined:
                by_company = refined
        if len(by_company) == 1:
            return MatchResult(matched=by_company[0])
        if len(by_company) > 1:
            return _clarify(by_company, max_candidates)

    # (c) position contains
    if position_n:
        by_pos = [
            j
            for j in active
            if position_n in _norm(_attr(j, "position"))
            or _norm(_attr(j, "position")) in position_n
        ]
        if len(by_pos) == 1:
            return MatchResult(matched=by_pos[0])
        if len(by_pos) > 1:
            return _clarify(by_pos, max_candidates)

    # (d) most recent as soft fallback when company hint partially matched nothing
    ranked = _sort_recent(active)
    if company_n or position_n:
        # Hints given but no match
        return MatchResult(candidates=[], need_clarify=True)
    return _clarify(ranked, max_candidates)


def _sort_recent(jobs: Sequence[Any]) -> list[Any]:
    def key(j: Any) -> str:
        for field in ("updated_at", "last_status_changed_at", "created_at"):
            v = _attr(j, field)
            if v is not None:
                return str(v)
        return ""

    return sorted(jobs, key=key, reverse=True)


def _clarify(jobs: Sequence[Any], max_candidates: int) -> MatchResult:
    ranked = _sort_recent(jobs)
    if len(ranked) > max_candidates:
        return MatchResult(
            candidates=list(ranked[:max_candidates]),
            need_clarify=True,
            too_many=True,
        )
    return MatchResult(candidates=list(ranked), need_clarify=True)


__all__ = ["MatchResult", "match_jobs"]
