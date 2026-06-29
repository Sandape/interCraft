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

    async def test_get_row_with_v1_marker_returns_400_legacy_format(
        self, v2_client: httpx.AsyncClient
    ) -> None:
        """The legacy marker inside `data` JSONB triggers 400 LEGACY_FORMAT."""
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
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        payload = r.json()
        assert payload.get("error") == "LEGACY_FORMAT", payload
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
