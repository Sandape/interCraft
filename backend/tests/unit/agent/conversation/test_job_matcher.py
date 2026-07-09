"""Unit tests for job_matcher FR-007."""

from types import SimpleNamespace
from uuid import uuid4

from app.modules.agent.conversation.job_matcher import match_jobs


def _job(company, position, **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid4()),
        company=company,
        position=position,
        status=kw.get("status", "applied"),
        deleted_at=kw.get("deleted_at"),
        updated_at=kw.get("updated_at", "2026-07-01"),
        last_status_changed_at=kw.get("last_status_changed_at"),
    )


def test_exact_company_position():
    jobs = [
        _job("腾讯", "后端"),
        _job("字节跳动", "前端"),
    ]
    r = match_jobs(jobs, company="腾讯", position="后端")
    assert r.unique
    assert r.matched.company == "腾讯"


def test_company_contains_unique():
    jobs = [_job("字节跳动", "AI应用"), _job("腾讯", "后端")]
    r = match_jobs(jobs, company="字节")
    assert r.unique
    assert "字节" in r.matched.company


def test_ambiguous_lists_candidates():
    jobs = [
        _job("腾讯", "后端"),
        _job("腾讯", "前端"),
        _job("阿里", "Java"),
    ]
    r = match_jobs(jobs, company="腾讯")
    assert r.need_clarify
    assert r.candidates is not None
    assert len(r.candidates) == 2


def test_no_hint_single_job():
    jobs = [_job("唯一", "岗")]
    r = match_jobs(jobs)
    assert r.unique


def test_no_hint_multi_clarify():
    jobs = [_job("A", "1"), _job("B", "2")]
    r = match_jobs(jobs)
    assert r.need_clarify
    assert len(r.candidates) == 2


def test_job_id_direct():
    jid = uuid4()
    jobs = [_job("X", "Y", id=jid), _job("Z", "W")]
    r = match_jobs(jobs, job_id=jid)
    assert r.unique
    assert r.matched.id == jid


def test_max_five_candidates():
    jobs = [_job(f"C{i}", "P") for i in range(8)]
    r = match_jobs(jobs, company="C")  # all contain? actually company exact-ish
    # company "C" contains in C0..C7 via "in"
    assert r.need_clarify
    assert len(r.candidates) <= 5
    assert r.too_many
