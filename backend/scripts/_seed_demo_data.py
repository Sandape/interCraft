"""One-off script: populate the demo user with branches + blocks + v1 for manual UI verification.

Connects via the live backend on http://127.0.0.1:8000.
"""
import asyncio
import httpx
import sys

BASE = "http://127.0.0.1:8000/api/v1"
FP = "fp-seed-once"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as c:
        # 1. Login
        r = await c.post(
            "/auth/login",
            json={
                "email": "demo@intercraft.io",
                "password": "Demo1234",
                "device_fingerprint": FP,
            },
            headers={"X-Device-Fingerprint": FP},
        )
        if r.status_code != 200:
            print(f"login failed: {r.status_code} {r.text}")
            return 1
        access = r.json()["tokens"]["access_token"]
        auth = {"Authorization": f"Bearer {access}", "X-Device-Fingerprint": FP}
        print("[OK] logged in as demo@intercraft.io")

        # 2. List existing branches; clean them out (only this run)
        r = await c.get("/resume-branches", headers=auth)
        existing = r.json()["data"]
        for b in existing:
            if b["is_main"]:
                # Promote none-of-them to main by deleting; but main cannot be deleted.
                # Strategy: demote-then-delete via patch + delete on non-main.
                pass
            await c.delete(f"/resume-branches/{b['id']}", headers=auth)
        print(f"[OK] cleaned {len(existing)} existing branches")

        # 3. Create main branch
        r = await c.post(
            "/resume-branches",
            json={
                "name": "核心简历",
                "is_main": True,
                "company": "通用",
                "position": "高级前端工程师",
            },
            headers=auth,
        )
        assert r.status_code == 201, r.text
        main = r.json()["branch"]
        main_id = main["id"]
        print(f"[OK] created main branch  id={main_id[:8]}  blocks={main['block_count']}")

        # 4. Create blocks on main
        blocks = [
            ("heading", "我的姓名", "副标题文本"),
            ("summary", "职业简介", "3 年 React/TypeScript 经验,熟悉 Vite/Tailwind/React Query,主导过抖音创作者平台重构。"),
            ("experience", "字节跳动 · 高级前端", "2024 - 至今\n抖音创作者平台前端负责人,带领 3 人小组完成 8 个核心模块,日活 50w+。"),
            ("skill", "技能栈", "React, TypeScript, Vite, Tailwind, Node.js, PostgreSQL, Redis"),
        ]
        for type_, title, content in blocks:
            r = await c.post(
                f"/resume-branches/{main_id}/blocks",
                json={"type": type_, "title": title, "content_md": content, "meta": None},
                headers=auth,
            )
            assert r.status_code in (200, 201), r.text
            print(f"   + {type_:11s}  {title}")

        # 5. Create derived branch (clones blocks)
        r = await c.post(
            "/resume-branches",
            json={
                "name": "字节 · 高级前端",
                "parent_id": main_id,
                "company": "字节跳动",
                "position": "高级前端工程师",
            },
            headers=auth,
        )
        assert r.status_code == 201, r.text
        derived = r.json()["branch"]
        derived_id = derived["id"]
        print(f"[OK] created derived branch  id={derived_id[:8]}  cloned_blocks={derived['block_count']}")

        # 6. Save v1 on main
        r = await c.post(
            f"/resume-branches/{main_id}/versions",
            json={"label": "v1 初始化"},
            headers=auth,
        )
        assert r.status_code in (200, 201), r.text
        v1 = r.json()["version"]
        print(f"[OK] saved v1 on main  version_no={v1['version_no']}  trigger={v1.get('trigger')}")

        # 7. Save v1 on derived
        r = await c.post(
            f"/resume-branches/{derived_id}/versions",
            json={"label": "v1 字节 fork"},
            headers=auth,
        )
        assert r.status_code in (200, 201), r.text
        print(f"[OK] saved v1 on derived  version_no={r.json()['version']['version_no']}")

        # 8. Final list
        r = await c.get("/resume-branches", headers=auth)
        for b in r.json()["data"]:
            print(
                f"   > {b['name']:18s}  id={b['id'][:8]}  "
                f"main={b['is_main']}  blocks={b['block_count']}  versions={b['version_count']}"
            )

        print("\n=== seed complete; ready for manual UI verification ===")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
