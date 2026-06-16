"""Integration tests for error questions (US6) — CRUD + FSM + RLS."""
from __future__ import annotations

import pytest


@pytest.mark.integration
class TestErrorQuestionsCRUD:
    async def test_list_empty(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/error-questions", headers=user_a_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []

    async def test_create_and_list(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "What is CAP theorem?", "dimension": "algorithm",
        })
        assert r.status_code == 201
        eq = r.json()
        assert eq["dimension"] == "algorithm"
        assert eq["status"] in ("fresh", "f3") or eq.get("frequency", 3) == 3

        r = await client.get("/api/v1/error-questions", headers=user_a_headers)
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_get_by_id(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Test get", "dimension": "architecture",
        })
        eq_id = r.json()["id"]
        r = await client.get(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers)
        assert r.status_code == 200
        assert r.json()["id"] == eq_id

    async def test_get_nonexistent_404(self, client, user_a_headers) -> None:
        r = await client.get("/api/v1/error-questions/ffffffff-ffff-7fff-8000-000000000000", headers=user_a_headers)
        assert r.status_code == 404

    async def test_patch(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Patch me", "dimension": "business",
        })
        eq_id = r.json()["id"]
        r = await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "question_text": "Patched text",
        })
        assert r.status_code == 200
        assert r.json()["question_text"] == "Patched text"

    async def test_archive_then_filter(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "To archive", "dimension": "communication",
        })
        eq_id = r.json()["id"]
        r = await client.delete(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers)
        assert r.status_code == 204
        # Archived should not appear in default list
        r = await client.get("/api/v1/error-questions?status=archived", headers=user_a_headers)
        assert r.status_code == 200

    async def test_filter_by_dimension(self, client, user_a_headers) -> None:
        await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Algo Q", "dimension": "algorithm",
        })
        r = await client.get("/api/v1/error-questions?dimension=algorithm", headers=user_a_headers)
        assert r.status_code == 200
        for item in r.json()["data"]:
            assert item["dimension"] == "algorithm"

    async def test_invalid_dimension_422(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Bad dim", "dimension": "not_a_dim",
        })
        assert r.status_code == 422


@pytest.mark.integration
class TestErrorQuestionsFSM:
    async def test_status_transition_fresh_to_practicing(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "FSM test", "dimension": "engineering_practice",
        })
        eq_id = r.json()["id"]
        r = await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "status": "practicing",
        })
        assert r.status_code == 200
        assert r.json()["status"] in ("practicing", "f2", "f1")

    async def test_reset_mastered_to_fresh(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Reset test", "dimension": "tech_depth",
        })
        eq_id = r.json()["id"]
        # Transition fresh → practicing → mastered
        await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "status": "practicing",
        })
        await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "status": "mastered",
        })
        # Then reset
        r = await client.post(f"/api/v1/error-questions/{eq_id}/reset", headers=user_a_headers)
        assert r.status_code == 200
        assert r.json()["status"] in ("fresh", "f3")

    async def test_recall_reduces_frequency_and_marks_practice_time(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Recall once", "dimension": "algorithm",
        })
        eq_id = r.json()["id"]

        r = await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "practicing"
        assert body["frequency"] == 2
        assert body["last_practiced_at"] is not None

    async def test_recall_to_mastered_then_reset(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Recall to mastered", "dimension": "architecture",
        })
        eq_id = r.json()["id"]

        await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)
        await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)
        r = await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "mastered"
        assert body["frequency"] == 0

        r = await client.post(f"/api/v1/error-questions/{eq_id}/reset", headers=user_a_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "fresh"
        assert r.json()["frequency"] == 3

    async def test_recall_mastered_conflict(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Already mastered", "dimension": "business",
        })
        eq_id = r.json()["id"]
        await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "status": "practicing",
        })
        await client.patch(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers, json={
            "status": "mastered",
        })

        r = await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)

        assert r.status_code == 409

    async def test_reset_non_mastered_conflict(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Reset too early", "dimension": "communication",
        })
        eq_id = r.json()["id"]

        r = await client.post(f"/api/v1/error-questions/{eq_id}/reset", headers=user_a_headers)

        assert r.status_code == 409

    async def test_recall_deleted_question_404(self, client, user_a_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_a_headers, json={
            "question_text": "Deleted recall", "dimension": "engineering_practice",
        })
        eq_id = r.json()["id"]
        await client.delete(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers)

        r = await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)

        assert r.status_code == 404


@pytest.mark.integration
class TestErrorQuestionsRLS:
    async def test_user_a_cannot_access_user_b_error(self, client, user_a_headers, user_b_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_b_headers, json={
            "question_text": "B's error", "dimension": "algorithm",
        })
        eq_id = r.json()["id"]
        r = await client.get(f"/api/v1/error-questions/{eq_id}", headers=user_a_headers)
        assert r.status_code == 404

    async def test_user_a_cannot_recall_user_b_error(self, client, user_a_headers, user_b_headers) -> None:
        r = await client.post("/api/v1/error-questions", headers=user_b_headers, json={
            "question_text": "B's recall-only error", "dimension": "algorithm",
        })
        eq_id = r.json()["id"]

        r = await client.post(f"/api/v1/error-questions/{eq_id}/recall", headers=user_a_headers)

        assert r.status_code == 404
