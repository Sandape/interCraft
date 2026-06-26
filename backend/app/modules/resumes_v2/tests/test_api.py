"""T018 — Resume v2 REST API contract tests.

Uses the in-process FastAPI app (ASGITransport) and the live auth flow to
mint real JWTs. The 14 endpoints under `/api/v1/v2/*` currently return
`501 NOT_IMPLEMENTED` (Wave 1 stubs); these tests pin the **expected
post-implementation** behavior and will FAIL with 501 in Wave 2, then
PASS in Wave 3 when the service layer ships.

Coverage:
- POST /resumes 201 + body shape
- POST 400 INVALID_SLUG on bad slug
- POST 409 SLUG_TAKEN on duplicate slug
- GET /resumes 200 list
- GET /resumes/{id} 200 detail
- GET /resumes/{id} 403 NOT_OWNER
- GET /resumes/{id} 404 NOT_FOUND
- PUT /resumes/{id} 400 MISSING_IF_MATCH
- PUT /resumes/{id} 200 with If-Match + version bump
- PUT /resumes/{id} 409 + {error, latest_version, latest_data} on stale If-Match
- PUT /resumes/{id} 423 RESUME_LOCKED
- DELETE /resumes/{id} 204
- Soft-deleted resume -> 404 on GET

T018 — authored in Wave 2, awaiting US1 implementation. Expect 501
failures on every assertion in this run; Wave 3 makes them pass.
"""
from __future__ import annotations

import secrets
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.modules.resumes_v2.tests.conftest import minimal_resume_data_v2


pytestmark = pytest.mark.integration


# ── helpers ────────────────────────────────────────────────────────────────

def auth_headers(user: dict[str, str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {user['access']}",
        "X-Device-Fingerprint": "fp-test",
        "X-Request-ID": f"req-{secrets.token_hex(6)}",
    }


@pytest.fixture
async def v2_client() -> httpx.AsyncClient:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── 1. POST /resumes ──────────────────────────────────────────────────────

class TestCreateResume:
    async def test_post_creates_resume_returns_201_with_full_body(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        body = {
            "name": "Senior Engineer",
            "slug": f"senior-eng-{secrets.token_hex(4)}",
            "template": "pikachu",
            "from_sample": True,
        }
        r = await v2_client.post("/api/v1/v2/resumes", json=body, headers=auth_headers(v2_user))
        assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
        payload = r.json()
        # Per contracts/01-rest-api.md §1.3
        for key in (
            "id", "user_id", "name", "slug", "tags",
            "is_public", "is_locked", "password_set",
            "data", "version", "created_at", "updated_at",
        ):
            assert key in payload, f"missing key {key} in response"
        assert payload["name"] == body["name"]
        assert payload["slug"] == body["slug"]
        assert payload["version"] == 0
        assert payload["is_public"] is False
        assert payload["is_locked"] is False
        assert payload["password_set"] is False
        assert payload["data"]["metadata"]["template"] == "pikachu"

    async def test_post_with_invalid_slug_returns_400(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """Per data-model.md §8.1: slug must match `^[a-z0-9-]+$`, 1..64 chars."""
        body = {
            "name": "Has Spaces",
            "slug": "Has Spaces!!!",  # spaces + non-allowed chars
            "template": "pikachu",
            "from_sample": True,
        }
        r = await v2_client.post("/api/v1/v2/resumes", json=body, headers=auth_headers(v2_user))
        assert r.status_code == 400, f"expected 400 INVALID_SLUG, got {r.status_code}: {r.text}"
        payload = r.json()
        assert payload.get("error") == "INVALID_SLUG"

    async def test_post_with_taken_slug_returns_409(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        slug = f"taken-{secrets.token_hex(4)}"
        body = {"name": "First", "slug": slug, "template": "pikachu", "from_sample": True}
        first = await v2_client.post("/api/v1/v2/resumes", json=body, headers=auth_headers(v2_user))
        assert first.status_code == 201, (
            f"first POST should succeed to set up the 409, got {first.status_code}: {first.text}"
        )
        # Second POST with the same slug must 409
        body2 = {"name": "Second", "slug": slug, "template": "pikachu", "from_sample": True}
        r = await v2_client.post("/api/v1/v2/resumes", json=body2, headers=auth_headers(v2_user))
        assert r.status_code == 409, f"expected 409 SLUG_TAKEN, got {r.status_code}: {r.text}"
        payload = r.json()
        assert payload.get("error") == "SLUG_TAKEN"


# ── 2. GET /resumes (list) ────────────────────────────────────────────────

class TestListResumes:
    async def test_list_returns_200_with_data_array(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        r = await v2_client.get("/api/v1/v2/resumes", headers=auth_headers(v2_user))
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        payload = r.json()
        assert "data" in payload
        assert isinstance(payload["data"], list)


# ── 3. GET /resumes/{id} ──────────────────────────────────────────────────

class TestGetResume:
    async def test_get_returns_200_with_full_body(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        created = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "Detail",
                "slug": f"detail-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert created.status_code == 201, created.text
        new_id = created.json()["id"]

        r = await v2_client.get(f"/api/v1/v2/resumes/{new_id}", headers=auth_headers(v2_user))
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["id"] == new_id
        assert payload["data"]["metadata"]["template"] == "pikachu"

    async def test_get_other_users_resume_returns_403(
        self,
        v2_client: httpx.AsyncClient,
        v2_user: dict[str, str],
        v2_user_b: dict[str, str],
    ) -> None:
        # User A creates a resume
        created = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "Secret",
                "slug": f"sec-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert created.status_code == 201, created.text
        new_id = created.json()["id"]

        # User B tries to GET it
        r = await v2_client.get(f"/api/v1/v2/resumes/{new_id}", headers=auth_headers(v2_user_b))
        assert r.status_code == 403, f"expected 403 NOT_OWNER, got {r.status_code}: {r.text}"
        assert r.json().get("error") == "NOT_OWNER"

    async def test_get_nonexistent_returns_404(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        r = await v2_client.get(
            "/api/v1/v2/resumes/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"
        assert r.json().get("error") == "NOT_FOUND"


# ── 4. PUT /resumes/{id} (optimistic concurrency) ────────────────────────

class TestUpdateResume:
    async def _create(self, v2_client, v2_user) -> dict[str, Any]:
        r = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "Upd",
                "slug": f"upd-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 201, r.text
        return r.json()

    async def test_put_without_if_match_returns_400(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        created = await self._create(v2_client, v2_user)
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"name": "NewName"},
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert r.json().get("error") == "MISSING_IF_MATCH"

    async def test_put_with_if_match_bumps_version(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        created = await self._create(v2_client, v2_user)
        headers = auth_headers(v2_user)
        headers["If-Match"] = "0"
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"name": "AfterPut"},
            headers=headers,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        payload = r.json()
        assert payload["version"] == 1, f"version should bump 0 -> 1, got {payload['version']}"
        assert payload["name"] == "AfterPut"

    async def test_put_with_stale_if_match_returns_409_with_latest(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """A 409 response MUST include {error, latest_version, latest_data,
        latest_updated_at} per contracts/01-rest-api.md §1.4."""
        created = await self._create(v2_client, v2_user)

        # First PUT: v0 -> v1
        h = auth_headers(v2_user)
        h["If-Match"] = "0"
        ok = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"name": "BumpTo1"},
            headers=h,
        )
        assert ok.status_code == 200, ok.text

        # Second PUT with stale v0: must 409
        h2 = auth_headers(v2_user)
        h2["If-Match"] = "0"
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"name": "StaleAttempt"},
            headers=h2,
        )
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
        payload = r.json()
        assert payload.get("error") == "VERSION_CONFLICT"
        assert payload.get("latest_version") == 1
        assert "latest_data" in payload
        assert "latest_updated_at" in payload
        # The conflict body must contain the full current data so the client
        # can re-apply local edits on top of it.
        assert payload["latest_data"]["metadata"]["template"] == "pikachu"

    async def test_put_when_locked_returns_423(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        created = await self._create(v2_client, v2_user)
        # Owner locks it
        lock = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}/lock",
            json={"locked": True},
            headers=auth_headers(v2_user),
        )
        assert lock.status_code == 200, lock.text

        # PUT must be rejected
        h = auth_headers(v2_user)
        h["If-Match"] = "0"
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"name": "ShouldFail"},
            headers=h,
        )
        assert r.status_code == 423, f"expected 423 RESUME_LOCKED, got {r.status_code}: {r.text}"
        assert r.json().get("error") == "RESUME_LOCKED"


# ── 4b. PUT partial deep-merge (REQ-039) ──────────────────────────────────

class TestUpdateResumePartialMerge:
    """REQ-039 — Phase B of the REQ-034 fix.

    The frontend ships partial PUTs (e.g. just ``metadata.template``)
    that the strict Pydantic schema cannot validate as a full
    ``ResumeDataV2``. The service layer (``merge_resume_data``) deep-
    merges the partial into the stored full doc, falling back unknown
    template ids to the default.
    """

    async def _create(self, v2_client, v2_user) -> dict[str, Any]:
        r = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "Partial",
                "slug": f"partial-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 201, r.text
        # Per locked API contract (REQ-032 envelope): create response
        # is `{"resume": {...}}`, not a flat dict.
        return r.json()["resume"]

    async def test_put_partial_template_unknown_id_falls_back_to_pikachu(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """PUT ``{"data": {"metadata": {"template": "<bogus>"}}}`` →
        200 OK, stored template = "pikachu" (default fallback)."""
        created = await self._create(v2_client, v2_user)
        h = auth_headers(v2_user)
        h["If-Match"] = str(created["version"])
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"data": {"metadata": {"template": "definitely-not-a-template"}}},
            headers=h,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["data"]["metadata"]["template"] == "pikachu"

    async def test_put_partial_template_known_id_applied(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """PUT ``{"data": {"metadata": {"template": "azurill"}}}`` →
        200 OK, stored template = "azurill" (legal value)."""
        created = await self._create(v2_client, v2_user)
        h = auth_headers(v2_user)
        h["If-Match"] = str(created["version"])
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={"data": {"metadata": {"template": "azurill"}}},
            headers=h,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["data"]["metadata"]["template"] == "azurill"

    async def test_put_partial_sections_deep_merge_preserves_other_sections(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """PUT only ``sections.skills.items`` → other sections (profiles,
        experience, etc.) are preserved from the stored doc."""
        created = await self._create(v2_client, v2_user)
        h = auth_headers(v2_user)
        h["If-Match"] = str(created["version"])
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={
                "data": {
                    "sections": {
                        "skills": {
                            "items": [
                                {
                                    "id": "skill-1",
                                    "hidden": False,
                                    "name": "Go",
                                    "level": 4,
                                }
                            ]
                        }
                    }
                }
            },
            headers=h,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        # skills.items updated
        assert len(body["data"]["sections"]["skills"]["items"]) == 1
        assert body["data"]["sections"]["skills"]["items"][0]["name"] == "Go"
        # other sections preserved
        for sec in (
            "profiles",
            "experience",
            "education",
            "projects",
            "languages",
            "interests",
            "awards",
            "certifications",
            "publications",
            "volunteer",
            "references",
        ):
            assert sec in body["data"]["sections"], f"section {sec} was lost"
            assert "title" in body["data"]["sections"][sec]

    async def test_put_partial_multi_key_preserves_unrelated_fields(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        """PUT ``metadata.template="onyx" + basics.name="New Name"`` →
        both fields update; other basics fields (email, phone, etc.)
        are preserved from the stored doc."""
        created = await self._create(v2_client, v2_user)
        # Capture the pre-existing email from the from_sample default
        original_email = created["data"]["basics"]["email"]
        h = auth_headers(v2_user)
        h["If-Match"] = str(created["version"])
        r = await v2_client.put(
            f"/api/v1/v2/resumes/{created['id']}",
            json={
                "data": {
                    "metadata": {"template": "onyx"},
                    "basics": {"name": "New Name"},
                }
            },
            headers=h,
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["data"]["metadata"]["template"] == "onyx"
        assert body["data"]["basics"]["name"] == "New Name"
        # email preserved
        assert body["data"]["basics"]["email"] == original_email
        # metadata sub-trees (layout/page/design/typography) preserved
        assert "layout" in body["data"]["metadata"]
        assert "page" in body["data"]["metadata"]
        assert "design" in body["data"]["metadata"]
        assert "typography" in body["data"]["metadata"]


# ── 5. DELETE /resumes/{id} ───────────────────────────────────────────────

class TestDeleteResume:
    async def test_delete_returns_204(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        r = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "ToDelete",
                "slug": f"del-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 201, r.text
        new_id = r.json()["id"]

        d = await v2_client.delete(
            f"/api/v1/v2/resumes/{new_id}", headers=auth_headers(v2_user)
        )
        assert d.status_code == 204, f"expected 204, got {d.status_code}: {d.text}"

    async def test_get_after_delete_returns_404(
        self, v2_client: httpx.AsyncClient, v2_user: dict[str, str]
    ) -> None:
        r = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "Gone",
                "slug": f"gone-{secrets.token_hex(4)}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=auth_headers(v2_user),
        )
        assert r.status_code == 201, r.text
        new_id = r.json()["id"]

        d = await v2_client.delete(
            f"/api/v1/v2/resumes/{new_id}", headers=auth_headers(v2_user)
        )
        assert d.status_code == 204, d.text

        g = await v2_client.get(
            f"/api/v1/v2/resumes/{new_id}", headers=auth_headers(v2_user)
        )
        assert g.status_code == 404, f"expected 404, got {g.status_code}: {g.text}"
        assert g.json().get("error") == "NOT_FOUND"
