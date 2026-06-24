"""027 US6 T086 — resume list_branches search/filter/sort.

GET /api/v1/resume-branches:
- search: ILIKE across name/company/position
- status_filter: comma-separated multi-status filter
- sort: edited (default) / created / match_score
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestResumeListSearchFilterSort:
    async def test_search_by_name_matches(self, client, user_a_headers) -> None:
        # create branches with distinct names
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "字节 · 前端", "company": "ByteDance", "position": "FE"},
        )
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "阿里 · 后端", "company": "Alibaba", "position": "BE"},
        )
        r = await client.get(
            "/api/v1/resume-branches?search=字节", headers=user_a_headers
        )
        assert r.status_code == 200, r.text
        names = [b["name"] for b in r.json()["data"]]
        assert any("字节" in n for n in names), names
        assert not any("阿里" in n for n in names), names

    async def test_search_by_company(self, client, user_a_headers) -> None:
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "n1", "company": "ByteDance", "position": "FE"},
        )
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "n2", "company": "Alibaba", "position": "BE"},
        )
        r = await client.get(
            "/api/v1/resume-branches?search=alibaba", headers=user_a_headers
        )
        names = [b["name"] for b in r.json()["data"]]
        assert "n2" in names
        assert "n1" not in names

    async def test_search_by_position(self, client, user_a_headers) -> None:
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "n1", "company": "C1", "position": "frontend-engineer"},
        )
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "n2", "company": "C2", "position": "devops"},
        )
        r = await client.get(
            "/api/v1/resume-branches?search=engineer", headers=user_a_headers
        )
        names = [b["name"] for b in r.json()["data"]]
        assert "n1" in names
        assert "n2" not in names

    async def test_status_filter_single(self, client, user_a_headers) -> None:
        # create branch then patch its status to "ready"
        r = await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "ready-one", "company": "C", "position": "P"},
        )
        bid = r.json()["branch"]["id"]
        await client.patch(
            f"/api/v1/resume-branches/{bid}",
            headers=user_a_headers,
            json={"status": "ready"},
        )
        # also create a draft branch
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "draft-one", "company": "C2", "position": "P2"},
        )
        r = await client.get(
            "/api/v1/resume-branches?status_filter=ready", headers=user_a_headers
        )
        names = [b["name"] for b in r.json()["data"]]
        assert "ready-one" in names
        assert "draft-one" not in names

    async def test_status_filter_multi(self, client, user_a_headers) -> None:
        # create three branches: draft, optimizing, ready
        created = []
        for name, status in [("d1", "draft"), ("o1", "optimizing"), ("r1", "ready")]:
            r = await client.post(
                "/api/v1/resume-branches",
                headers=user_a_headers,
                json={"name": name, "company": "C", "position": "P"},
            )
            bid = r.json()["branch"]["id"]
            if status != "draft":
                await client.patch(
                    f"/api/v1/resume-branches/{bid}",
                    headers=user_a_headers,
                    json={"status": status},
                )
            created.append(name)
        r = await client.get(
            "/api/v1/resume-branches?status_filter=draft,ready",
            headers=user_a_headers,
        )
        names = [b["name"] for b in r.json()["data"]]
        assert "d1" in names
        assert "r1" in names
        assert "o1" not in names

    async def test_sort_by_created(self, client, user_a_headers) -> None:
        # create branches in order; latest should come first under created sort
        # (but is_pinned/is_main still take precedence)
        for i in range(3):
            await client.post(
                "/api/v1/resume-branches",
                headers=user_a_headers,
                json={"name": f"sort-c-{i}", "company": f"c{i}", "position": "p"},
            )
        r = await client.get(
            "/api/v1/resume-branches?sort=created",
            headers=user_a_headers,
        )
        names = [b["name"] for b in r.json()["data"] if b["name"].startswith("sort-c-")]
        assert names == ["sort-c-2", "sort-c-1", "sort-c-0"], names

    async def test_sort_by_edited_default(self, client, user_a_headers) -> None:
        # default sort = edited; recent edit first
        ids = []
        for i in range(3):
            r = await client.post(
                "/api/v1/resume-branches",
                headers=user_a_headers,
                json={"name": f"sort-e-{i}", "company": f"c{i}", "position": "p"},
            )
            ids.append(r.json()["branch"]["id"])
        # patch the oldest to bump last_edited_at
        await client.patch(
            f"/api/v1/resume-branches/{ids[0]}",
            headers=user_a_headers,
            json={"name": "sort-e-0-bumped"},
        )
        r = await client.get(
            "/api/v1/resume-branches",
            headers=user_a_headers,
        )
        names = [b["name"] for b in r.json()["data"] if "sort-e" in b["name"]]
        # bumped should be earlier than 1 and 2
        assert names.index("sort-e-0-bumped") < names.index("sort-e-1"), names

    async def test_search_is_case_insensitive(self, client, user_a_headers) -> None:
        await client.post(
            "/api/v1/resume-branches",
            headers=user_a_headers,
            json={"name": "ByTeDance", "company": "x", "position": "y"},
        )
        r = await client.get(
            "/api/v1/resume-branches?search=BYTEDANCE", headers=user_a_headers
        )
        names = [b["name"] for b in r.json()["data"]]
        assert "ByTeDance" in names
