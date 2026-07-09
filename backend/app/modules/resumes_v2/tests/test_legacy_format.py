"""T125 — v1 legacy format detection on GET /api/v1/v2/resumes/{id}.

US15 / FR-073. When a v2 row's `data` JSONB has
``data_format_version == 'v1'``, the GET endpoint must return 400
LEGACY_FORMAT so the frontend can show a read-only banner + redirect
suggestion. New v2 rows do NOT have this key.

Strategy: we insert a row directly via the raw DB fixture with a
`data_format_version: 'v1'` marker in the JSONB, then hit GET and
assert the 400 envelope. The raw insert avoids needing a real v1
write path (the v1 module is in a different table; the marker is
the canonical signal).
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.modules.resumes_v2.tests.conftest import (
    insert_resume_v2_raw,
    minimal_resume_data_v2,
)
from app.modules.resumes_v2.tests.conftest import _hdrs  # type: ignore[attr-defined]


pytestmark = pytest.mark.integration


@pytest.fixture
async def v2_client() -> httpx.AsyncClient:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register_via(c: httpx.AsyncClient, email: str, fp: str) -> dict[str, str]:
    r = await c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": email.split("@")[0],
            "device_fingerprint": fp,
        },
        headers=_hdrs(fp=fp),
    )
    body = r.json()
    return {"user_id": body["user"]["id"], "access": body["tokens"]["access_token"]}


class TestLegacyFormatDetection:
    async def test_get_v2_resume_without_marker_returns_200(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """Baseline: a v2 row (no marker) is returned normally."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"t125-ok-{suffix}@intercraft.io",
            f"fp-t125-ok-{suffix}",
        )
        # Create a v2 resume via the public API.
        r = await v2_client.post(
            "/api/v1/v2/resumes",
            json={
                "name": "V2 Normal",
                "slug": f"t125-ok-{suffix}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=_hdrs(access=user["access"]),
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        r = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("data") is not None

    async def test_get_row_with_v1_marker_returns_staged_markdown(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """The legacy marker stages Markdown for the cutover editor."""
        from uuid import UUID

        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"t125-legacy-{suffix}@intercraft.io",
            f"fp-t125-legacy-{suffix}",
        )
        # We need a raw session to seed a row whose `data` JSONB carries
        # the legacy marker. Use the root conftest's `db_session` via
        # the in-process engine.
        from app.core.db import _session_cm

        legacy_data = minimal_resume_data_v2()
        legacy_data["data_format_version"] = "v1"
        legacy_data["basics"]["name"] = "Legacy V1"
        legacy_data["basics"]["email"] = "legacy@example.com"
        legacy_data["summary"]["content"] = "<p>Legacy summary.</p>"

        async with _session_cm() as session:
            rid = await insert_resume_v2_raw(
                session,
                user_id=UUID(user["user_id"]),
                name="Legacy V1",
                slug=f"t125-legacy-{suffix}",
                data=legacy_data,
            )
            await session.commit()

        r = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        payload = r.json()
        markdown = payload["data"]["metadata"]["markdown"]
        assert markdown["legacyConversionStatus"] == "converted"
        assert "# Legacy V1" in markdown["sourceMarkdown"]
        assert "icon:email legacy@example.com" in markdown["sourceMarkdown"]
        assert "Legacy summary." in markdown["sourceMarkdown"]
        return
        # The message must be human-readable (used verbatim by the
        # frontend banner in T126).
        assert "v1" in payload.get("message", "").lower() or "旧版" in payload.get("message", "")

    async def test_get_v2_marker_returns_200_marker_ignored(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """Marker is exact-match on 'v1'; a 'v2' marker (or any other)
        must NOT trigger 400."""
        from uuid import UUID

        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"t125-v2marker-{suffix}@intercraft.io",
            f"fp-t125-v2m-{suffix}",
        )
        from app.core.db import _session_cm

        v2_data = minimal_resume_data_v2()
        v2_data["data_format_version"] = "v2"  # explicit v2 marker

        async with _session_cm() as session:
            rid = await insert_resume_v2_raw(
                session,
                user_id=UUID(user["user_id"]),
                name="V2 Explicit",
                slug=f"t125-v2marker-{suffix}",
                data=v2_data,
            )
            await session.commit()

        r = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"


# ── 5. REQ-034 US2 — Experience field round-trip ──────────────────────────
#
# AC-15 / AC-15-revised: PUT a complete `sections.experience.items[]`
# payload (3 items, each with 2 roles) and verify GET returns the exact
# same shape. Two extra cases:
#   (a) `hidden=true` field is preserved across round-trip.
#   (b) `description` containing HTML tags round-trips; storage currently
#       preserves verbatim while the renderer sanitises in the PDF path.

class TestExperienceRoundTrip:
    async def _create_via_api(
        self,
        c: httpx.AsyncClient,
        access: str,
        *,
        suffix: str,
    ) -> str:
        r = await c.post(
            "/api/v1/v2/resumes",
            json={
                "name": "ExpRoundTrip",
                "slug": f"exp-rt-{suffix}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=_hdrs(access=access),
        )
        assert r.status_code == 201, r.text
        # POST returns `{ "resume": {...} }` per the locked envelope
        # contract (see L021 / api.py:161).
        return r.json()["resume"]["id"]

    async def test_experience_full_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-15: PUT 3 experience items (each with 2 roles) → GET returns
        the same shape, including nested `roles[]`."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"exp-rt-{suffix}@intercraft.io",
            f"fp-exp-rt-{suffix}",
        )
        rid = await self._create_via_api(v2_client, user["access"], suffix=suffix)

        items = [
            {
                "id": f"e{i}-{suffix}",
                "hidden": False,
                "company": f"ACME {i}",
                "position": f"Engineer {i}",
                "location": f"City {i}",
                "period": f"202{i} - now",
                "website": {
                    "url": f"https://acme{i}.example.com",
                    "label": f"ACME {i}",
                    "inlineLink": i % 2 == 0,
                },
                "description": f"<p>Did things at ACME {i}.</p>",
                "roles": [
                    {
                        "id": f"e{i}-r1-{suffix}",
                        "position": "Senior",
                        "period": f"202{i}.01 - 202{i}.06",
                        "description": "<p>Lead a team.</p>",
                    },
                    {
                        "id": f"e{i}-r2-{suffix}",
                        "position": "Junior",
                        "period": f"202{i}.07 - 202{i}.12",
                        "description": "<p>Wrote some code.</p>",
                    },
                ],
            }
            for i in range(1, 4)
        ]
        h = _hdrs(access=user["access"])
        h["If-Match"] = "0"
        put = await v2_client.put(
            f"/api/v1/v2/resumes/{rid}",
            json={"data": {"sections": {"experience": {"items": items}}}},
            headers=h,
        )
        assert put.status_code == 200, f"expected 200, got {put.status_code}: {put.text}"

        got = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert got.status_code == 200, got.text
        got_items = got.json()["data"]["sections"]["experience"]["items"]
        assert len(got_items) == 3
        for idx, want in enumerate(items):
            assert got_items[idx]["id"] == want["id"]
            assert got_items[idx]["company"] == want["company"]
            assert got_items[idx]["position"] == want["position"]
            assert got_items[idx]["location"] == want["location"]
            assert got_items[idx]["period"] == want["period"]
            assert got_items[idx]["website"]["url"] == want["website"]["url"]
            assert got_items[idx]["website"]["label"] == want["website"]["label"]
            assert got_items[idx]["website"]["inlineLink"] == want["website"]["inlineLink"]
            assert got_items[idx]["description"] == want["description"]
            assert len(got_items[idx]["roles"]) == 2
            for r_idx, want_role in enumerate(want["roles"]):
                got_role = got_items[idx]["roles"][r_idx]
                assert got_role["id"] == want_role["id"]
                assert got_role["position"] == want_role["position"]
                assert got_role["period"] == want_role["period"]
                assert got_role["description"] == want_role["description"]

    async def test_experience_hidden_field_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-15-revised(a): a `hidden=true` item must round-trip."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"exp-hidden-{suffix}@intercraft.io",
            f"fp-exp-hidden-{suffix}",
        )
        rid = await self._create_via_api(v2_client, user["access"], suffix=suffix)
        items = [
            {
                "id": f"eh-{suffix}",
                "hidden": True,
                "company": "Hidden Co",
                "position": "Stealth",
                "location": "",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": "",
                "roles": [],
            }
        ]
        h = _hdrs(access=user["access"])
        h["If-Match"] = "0"
        put = await v2_client.put(
            f"/api/v1/v2/resumes/{rid}",
            json={"data": {"sections": {"experience": {"items": items}}}},
            headers=h,
        )
        assert put.status_code == 200, f"expected 200, got {put.status_code}: {put.text}"
        got = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert got.status_code == 200, got.text
        got_items = got.json()["data"]["sections"]["experience"]["items"]
        assert len(got_items) == 1
        assert got_items[0]["hidden"] is True
        assert got_items[0]["company"] == "Hidden Co"

    async def test_experience_description_html_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-15-revised(b): description HTML round-trips.

        The backend stores the description verbatim. The contract note
        in AC-15-revised(b) calls for sanitisation ("bleach / dompurify")
        to strip ``<script>`` tags. As of US2 ship, the sanitiser lives
        in the PDF renderer (`sanitize_html`) — the storage path keeps
        the raw HTML. This test pins BOTH the current behaviour and the
        known gap: if/when storage-side sanitisation ships, this test
        will be updated to assert the sanitised output and the assertion
        below (verbatim preservation) will be relaxed.
        """
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"exp-html-{suffix}@intercraft.io",
            f"fp-exp-html-{suffix}",
        )
        rid = await self._create_via_api(v2_client, user["access"], suffix=suffix)
        desc_in = "<p>foo</p><script>alert(1)</script>"
        items = [
            {
                "id": f"ed-{suffix}",
                "hidden": False,
                "company": "ACME",
                "position": "Engineer",
                "location": "",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": desc_in,
                "roles": [],
            }
        ]
        h = _hdrs(access=user["access"])
        h["If-Match"] = "0"
        put = await v2_client.put(
            f"/api/v1/v2/resumes/{rid}",
            json={"data": {"sections": {"experience": {"items": items}}}},
            headers=h,
        )
        assert put.status_code == 200, f"expected 200, got {put.status_code}: {put.text}"
        got = await v2_client.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=user["access"]),
        )
        assert got.status_code == 200, got.text
        got_desc = got.json()["data"]["sections"]["experience"]["items"][0]["description"]
        # Storage contract today: verbatim preservation. Renderer-side
        # sanitisation is verified by `test_export.py` (PDF render path).
        assert got_desc
        assert got_desc == desc_in, (
            "description storage is verbatim; renderer-side sanitisation "
            "is exercised by test_export.py"
        )


# ── 6. REQ-034 US3 — Education / Project / Skill field round-trip ─────────
#
# AC-20 (R15): PUT complete sections.{education,projects,skills}.items[]
# payloads and verify GET returns the same shape. Six sub cases:
#   (a) education_full_roundtrip — 2 items with courses[] + website{}
#   (b) project_full_roundtrip — 2 items with highlights[] + website{}
#   (c) skill_full_roundtrip — 2 items with keywords[] + level=3
#   (d) education_description_html_sanitized — script tag round-trip
#   (e) project_description_html_sanitized
#   (f) skill_level_zero_roundtrip — schema accepts level=0
#   (g) education_hidden_field_roundtrip — hidden=true preserved
#   (h) project_highlights_empty_array_roundtrip — highlights=[] not null
#   (i) skill_keywords_empty_array_roundtrip — keywords=[] not null

class _Us3Base:
    """Shared helpers for US3 round-trip tests."""

    @staticmethod
    async def _create_via_api(
        c: httpx.AsyncClient,
        access: str,
        *,
        suffix: str,
        name: str,
    ) -> str:
        r = await c.post(
            "/api/v1/v2/resumes",
            json={
                "name": name,
                "slug": f"us3-{suffix}",
                "template": "pikachu",
                "from_sample": True,
            },
            headers=_hdrs(access=access),
        )
        assert r.status_code == 201, r.text
        return r.json()["resume"]["id"]

    @staticmethod
    async def _put_and_get(
        c: httpx.AsyncClient,
        rid: str,
        access: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        h = _hdrs(access=access)
        h["If-Match"] = "0"
        put = await c.put(
            f"/api/v1/v2/resumes/{rid}",
            json={"data": payload},
            headers=h,
        )
        assert put.status_code == 200, f"expected 200, got {put.status_code}: {put.text}"
        got = await c.get(
            f"/api/v1/v2/resumes/{rid}",
            headers=_hdrs(access=access),
        )
        assert got.status_code == 200, got.text
        return got.json()["data"]


class TestEducationRoundTrip(_Us3Base):
    async def test_education_full_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(a): PUT 2 education items with courses[] + website{} → GET deep-equal."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"edu-rt-{suffix}@intercraft.io",
            f"fp-edu-rt-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="EduRT"
        )
        items = [
            {
                "id": f"ed{i}-{suffix}",
                "hidden": False,
                "school": f"School {i}",
                "degree": "Bachelor",
                "area": "CS",
                "grade": "3.8/4.0",
                "location": f"City {i}",
                "period": "2018-09 ~ 2022-06",
                "website": {
                    "url": f"https://school{i}.example.com",
                    "label": f"School {i}",
                    "inlineLink": False,
                },
                "description": f"<p>Studied at School {i}.</p>",
                "courses": ["Algorithms", "OS", "Networks"],
            }
            for i in range(1, 3)
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"education": {"items": items}}},
        )
        got_items = data["sections"]["education"]["items"]
        assert len(got_items) == 2
        for idx, want in enumerate(items):
            for key in (
                "id", "school", "degree", "area", "grade", "location",
                "period", "description",
            ):
                assert got_items[idx][key] == want[key], key
            assert got_items[idx]["website"]["url"] == want["website"]["url"]
            assert got_items[idx]["website"]["label"] == want["website"]["label"]
            assert got_items[idx]["website"]["inlineLink"] == want["website"]["inlineLink"]
            assert got_items[idx]["courses"] == want["courses"]

    async def test_education_description_html_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(d): description containing <script> round-trips verbatim
        (same pattern as Experience — storage verbatim, renderer-side
        sanitisation via test_export.py)."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"edu-html-{suffix}@intercraft.io",
            f"fp-edu-html-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="EduHTML"
        )
        desc_in = "<p>foo</p><script>alert(1)</script>"
        items = [
            {
                "id": f"edhtml-{suffix}",
                "hidden": False,
                "school": "X",
                "degree": "",
                "area": "",
                "grade": "",
                "location": "",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": desc_in,
                "courses": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"education": {"items": items}}},
        )
        got_desc = data["sections"]["education"]["items"][0]["description"]
        assert got_desc
        assert got_desc == desc_in

    async def test_education_hidden_field_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(g): hidden=true is preserved on education item."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"edu-hidden-{suffix}@intercraft.io",
            f"fp-edu-hidden-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="EduHidden"
        )
        items = [
            {
                "id": f"edhidden-{suffix}",
                "hidden": True,
                "school": "Hidden U",
                "degree": "",
                "area": "",
                "grade": "",
                "location": "",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": "",
                "courses": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"education": {"items": items}}},
        )
        item = data["sections"]["education"]["items"][0]
        assert item["hidden"] is True
        assert item["school"] == "Hidden U"


class TestProjectRoundTrip(_Us3Base):
    async def test_project_full_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(b): PUT 2 project items with highlights[] + website{} → GET deep-equal."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pj-rt-{suffix}@intercraft.io",
            f"fp-pj-rt-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="ProjRT"
        )
        items = [
            {
                "id": f"pj{i}-{suffix}",
                "hidden": False,
                "name": f"Project {i}",
                "period": "2024-01 ~ Present",
                "website": {
                    "url": f"https://proj{i}.example.com",
                    "label": f"Proj {i}",
                    "inlineLink": True,
                },
                "description": f"<p>Built project {i}.</p>",
                "highlights": ["Did X", "Did Y", "Did Z"],
            }
            for i in range(1, 3)
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"projects": {"items": items}}},
        )
        got_items = data["sections"]["projects"]["items"]
        assert len(got_items) == 2
        for idx, want in enumerate(items):
            for key in ("id", "name", "period", "description"):
                assert got_items[idx][key] == want[key], key
            assert got_items[idx]["website"]["url"] == want["website"]["url"]
            assert got_items[idx]["highlights"] == want["highlights"]

    async def test_project_description_html_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(e): description containing <script> round-trips verbatim."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pj-html-{suffix}@intercraft.io",
            f"fp-pj-html-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="ProjHTML"
        )
        desc_in = "<p>foo</p><script>alert(1)</script>"
        items = [
            {
                "id": f"pjhtml-{suffix}",
                "hidden": False,
                "name": "X",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": desc_in,
                "highlights": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"projects": {"items": items}}},
        )
        got_desc = data["sections"]["projects"]["items"][0]["description"]
        assert got_desc
        assert got_desc == desc_in

    async def test_project_highlights_empty_array_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(h): highlights=[] round-trips as empty array, not null."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pj-empty-{suffix}@intercraft.io",
            f"fp-pj-empty-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="ProjEmpty"
        )
        items = [
            {
                "id": f"pjempty-{suffix}",
                "hidden": False,
                "name": "X",
                "period": "",
                "website": {"url": "", "label": "", "inlineLink": False},
                "description": "",
                "highlights": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"projects": {"items": items}}},
        )
        got_h = data["sections"]["projects"]["items"][0]["highlights"]
        assert got_h == [], f"expected empty array, got {got_h!r}"


class TestSkillRoundTrip(_Us3Base):
    async def test_skill_full_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(c): PUT 2 skill items with keywords[] + level=3 → GET deep-equal."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"sk-rt-{suffix}@intercraft.io",
            f"fp-sk-rt-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="SkillRT"
        )
        items = [
            {
                "id": f"sk{i}-{suffix}",
                "hidden": False,
                "icon": "wrench",
                "iconColor": "rgba(0,0,0,1)",
                "name": f"Skill {i}",
                "proficiency": "Fluent",
                "level": 3,
                "keywords": ["k1", "k2"],
            }
            for i in range(1, 3)
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"skills": {"items": items}}},
        )
        got_items = data["sections"]["skills"]["items"]
        assert len(got_items) == 2
        for idx, want in enumerate(items):
            for key in (
                "id", "icon", "iconColor", "name", "proficiency", "level",
            ):
                assert got_items[idx][key] == want[key], key
            assert got_items[idx]["keywords"] == want["keywords"]

    async def test_skill_level_zero_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(f): level=0 (Hidden semantic) round-trips — schema
        ``int = Field(ge=0, le=5)`` accepts 0."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"sk-zero-{suffix}@intercraft.io",
            f"fp-sk-zero-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="SkillZero"
        )
        items = [
            {
                "id": f"skzero-{suffix}",
                "hidden": False,
                "icon": "wrench",
                "iconColor": "rgba(0,0,0,1)",
                "name": "HiddenLvl",
                "proficiency": "",
                "level": 0,
                "keywords": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"skills": {"items": items}}},
        )
        item = data["sections"]["skills"]["items"][0]
        assert item["level"] == 0
        assert item["hidden"] is False  # level=0 ≠ hidden=true (independent)

    async def test_skill_keywords_empty_array_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-20(i): keywords=[] round-trips as empty array, not null."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"sk-empty-{suffix}@intercraft.io",
            f"fp-sk-empty-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="SkillEmpty"
        )
        items = [
            {
                "id": f"skempty-{suffix}",
                "hidden": False,
                "icon": "wrench",
                "iconColor": "rgba(0,0,0,1)",
                "name": "X",
                "proficiency": "",
                "level": 1,
                "keywords": [],
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"skills": {"items": items}}},
        )
        got_k = data["sections"]["skills"]["items"][0]["keywords"]
        assert got_k == [], f"expected empty array, got {got_k!r}"


# ── US4 (REQ-034) profile round-trip cases (AC-03, AC-05, AC-06, AC-08,
#    AC-09, AC-10, AC-15) ──────────────────────────────────────────────────


class TestProfileRoundTrip(_Us3Base):
    """ProfileItem backend round-trip coverage.

    Mirrors the frontend ProfileDialog AC matrix: full round-trip,
    URL scheme whitelist/blacklist, hidden field, icon whitelist
    passthrough, iconColor rgba round-trip, and free-form username
    (handles / phone / Chinese / URL).
    """

    async def test_profile_full_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-03: PUT a profile item, GET it back, all 7 fields match."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-full-{suffix}@intercraft.io",
            f"fp-pr-full-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="ProfileFull"
        )
        items = [
            {
                "id": f"prfull-{suffix}",
                "hidden": False,
                "icon": "github",
                "iconColor": "rgba(20,30,40,0.9)",
                "network": "GitHub",
                "username": "alice",
                "website": {
                    "url": "https://github.com/alice",
                    "label": "GH",
                    "inlineLink": True,
                },
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"profiles": {"items": items}}},
        )
        got = data["sections"]["profiles"]["items"][0]
        for key in (
            "id", "hidden", "icon", "iconColor", "network", "username",
        ):
            assert got[key] == items[0][key], key
        assert got["website"]["url"] == items[0]["website"]["url"]
        assert got["website"]["label"] == items[0]["website"]["label"]
        assert got["website"]["inlineLink"] is True

    async def test_profile_url_scheme_whitelist_and_blacklist(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-08: GET round-trip preserves the URL as-is (backend is
        passthrough — frontend dialog enforces whitelist/blacklist).
        Whitelisted schemes (https / tel / mailto / IPv6 / unicode host)
        round-trip byte-identical, proving the backend makes no
        transformation. The frontend rejects javascript: at write time
        so we only verify storage integrity here."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-url-{suffix}@intercraft.io",
            f"fp-pr-url-{suffix}",
        )
        for url in [
            "https://[::1]:8080",
            "tel:+86-010-1234",
            "mailto:a@b.com",
            "https://中文.cn",
        ]:
            iter_suffix = f"{suffix}-{secrets.token_hex(3)}"
            rid = await self._create_via_api(
                v2_client, user["access"], suffix=iter_suffix, name="ProfileUrl"
            )
            items = [
                {
                    "id": f"prurl-{iter_suffix}",
                    "hidden": False,
                    "icon": "github",
                    "iconColor": "rgba(0,0,0,1)",
                    "network": "X",
                    "username": "u",
                    "website": {"url": url, "label": "", "inlineLink": False},
                }
            ]
            data = await self._put_and_get(
                v2_client, rid, user["access"],
                {"sections": {"profiles": {"items": items}}},
            )
            got_url = data["sections"]["profiles"]["items"][0]["website"]["url"]
            assert got_url == url, f"expected {url!r}, got {got_url!r}"

    async def test_profile_hidden_field_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-19: hidden=true round-trips, and SectionItem should render
        the row with reduced opacity on the frontend."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-hidden-{suffix}@intercraft.io",
            f"fp-pr-hidden-{suffix}",
        )
        rid = await self._create_via_api(
            v2_client, user["access"], suffix=suffix, name="ProfileHidden"
        )
        items = [
            {
                "id": f"prhid-{suffix}",
                "hidden": True,
                "icon": "github",
                "iconColor": "rgba(0,0,0,1)",
                "network": "HiddenX",
                "username": "h",
                "website": {"url": "", "label": "", "inlineLink": False},
            }
        ]
        data = await self._put_and_get(
            v2_client, rid, user["access"],
            {"sections": {"profiles": {"items": items}}},
        )
        item = data["sections"]["profiles"]["items"][0]
        assert item["hidden"] is True
        assert item["network"] == "HiddenX"

    async def test_profile_icon_whitelist_passthrough(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-09: backend IconName is length-only (1..64). Whitelisted
        icons (``github`` / ``linkedin`` / ``twitter`` / ``facebook``)
        round-trip — the frontend enforces the semantic whitelist."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-icon-{suffix}@intercraft.io",
            f"fp-pr-icon-{suffix}",
        )
        for icon in ["github", "linkedin", "twitter", "facebook"]:
            iter_suffix = f"{suffix}-{secrets.token_hex(3)}"
            rid = await self._create_via_api(
                v2_client, user["access"], suffix=iter_suffix, name="ProfileIcon"
            )
            items = [
                {
                    "id": f"pricon-{iter_suffix}",
                    "hidden": False,
                    "icon": icon,
                    "iconColor": "rgba(0,0,0,1)",
                    "network": "N",
                    "username": "u",
                    "website": {"url": "", "label": "", "inlineLink": False},
                }
            ]
            data = await self._put_and_get(
                v2_client, rid, user["access"],
                {"sections": {"profiles": {"items": items}}},
            )
            got_icon = data["sections"]["profiles"]["items"][0]["icon"]
            assert got_icon == icon, f"expected {icon!r}, got {got_icon!r}"

    async def test_profile_icon_color_rgba_roundtrip(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-10 / AC-06: a hex picker value ``#ff0000`` is converted to
        ``rgba(255,0,0,1)`` on the frontend and stored verbatim. Verify
        the canonical rgba shape round-trips and an alpha < 1 is
        preserved."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-clr-{suffix}@intercraft.io",
            f"fp-pr-clr-{suffix}",
        )
        for color in [
            "rgba(0,0,0,1)",
            "rgba(255,0,0,1)",
            "rgba(20,30,40,0.5)",
            "rgba(255,255,255,0)",
        ]:
            iter_suffix = f"{suffix}-{secrets.token_hex(3)}"
            rid = await self._create_via_api(
                v2_client, user["access"], suffix=iter_suffix, name="ProfileColor"
            )
            items = [
                {
                    "id": f"prclr-{iter_suffix}",
                    "hidden": False,
                    "icon": "github",
                    "iconColor": color,
                    "network": "N",
                    "username": "u",
                    "website": {"url": "", "label": "", "inlineLink": False},
                }
            ]
            data = await self._put_and_get(
                v2_client, rid, user["access"],
                {"sections": {"profiles": {"items": items}}},
            )
            got_c = data["sections"]["profiles"]["items"][0]["iconColor"]
            assert got_c == color, f"expected {color!r}, got {got_c!r}"

    async def test_profile_username_free_format_passthrough(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """AC-05 / AC-08: username is free-form. Handles, phone numbers,
        Chinese names, and full URLs all round-trip verbatim."""
        suffix = secrets.token_hex(6)
        user = await _register_via(
            v2_client,
            f"pr-usr-{suffix}@intercraft.io",
            f"fp-pr-usr-{suffix}",
        )
        for username in [
            "foo@bar",
            "+86-138-0013-8000",
            "李祖荫",
            "https://github.com/foo",
        ]:
            iter_suffix = f"{suffix}-{secrets.token_hex(3)}"
            rid = await self._create_via_api(
                v2_client, user["access"], suffix=iter_suffix, name="ProfileUser"
            )
            items = [
                {
                    "id": f"prusr-{iter_suffix}",
                    "hidden": False,
                    "icon": "github",
                    "iconColor": "rgba(0,0,0,1)",
                    "network": "N",
                    "username": username,
                    "website": {"url": "", "label": "", "inlineLink": False},
                }
            ]
            data = await self._put_and_get(
                v2_client, rid, user["access"],
                {"sections": {"profiles": {"items": items}}},
            )
            got_u = data["sections"]["profiles"]["items"][0]["username"]
            assert got_u == username, f"expected {username!r}, got {got_u!r}"
