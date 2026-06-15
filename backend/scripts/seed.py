"""Seed a demo user with a rich resume dataset (idempotent).

Run via:
    uv run python -m scripts.seed
or:
    uv run python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make `app.*` importable when running from backend/ root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session_factory  # noqa: E402
from app.modules.auth.schemas import RegisterInput  # noqa: E402
from app.modules.auth.service import AuthService  # noqa: E402
from app.modules.resumes.service import ResumeService  # noqa: E402
from app.modules.versions.service import VersionService  # noqa: E402
from app.domain.rls import set_user_context  # noqa: E402

DEMO_EMAIL = "demo@intercraft.io"
DEMO_PASSWORD = "Demo1234"


async def run() -> None:
    settings = get_settings()
    if "PLACEHOLDER" in settings.database_url:
        raise SystemExit(
            "DATABASE_URL is a placeholder. Configure it in backend/.env (T008b)."
        )
    factory = get_session_factory()
    async with factory() as db:
        auth = AuthService(db)
        existing = await auth.users.get_by_email(DEMO_EMAIL)
        if existing is not None:
            print(f"seed: user {DEMO_EMAIL} already exists — checking for missing data")
            user = existing
            # Check if child branches already exist
            svc = ResumeService(db)
            branches = await svc.list_branches(user.id)
            if len(branches) > 1:
                print(f"seed: already has {len(branches)} branches — skipping seed")
                return
            # Otherwise add child branches and versions below
            main = branches[0] if branches else None
        else:
            # 1. Register demo user
            user, _ = await auth.register(
                RegisterInput(
                    email=DEMO_EMAIL,
                    password=DEMO_PASSWORD,
                    display_name="林浩然",
                )
            )
            print(f"seed: created user {user.id}")
            main = None

        # Set RLS context — seed runs outside HTTP request lifecycle
        await set_user_context(db, str(user.id))

        svc = ResumeService(db)
        version_svc = VersionService(db)

        # 2. Create main resume branch if needed
        if main is None:
            main = await svc.create_branch(
                user_id=user.id,
                name="核心简历",
                company=None,
                position="基础版本",
                parent_id=None,
                is_main=True,
            )
            await svc.patch_branch(main.id, user.id, status="ready")
            print(f"seed: created main branch {main.id}")

            # 3. Create 7 blocks on the main branch
            await svc.create_block(
                main.id, user.id,
                block_type="heading", title=user.display_name,
                content_md="# 林浩然 · 高级前端工程师\n北京 · 3 年经验 · haoran.lin@example.com",
                meta={"email": "haoran.lin@example.com", "phone": "138****0001"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="summary", title="个人简介",
                content_md="3 年大厂前端开发经验，专注于大型 SPA 性能优化与组件库架构设计。主导过从 0 到 1 的中后台系统搭建，熟悉 React 18 / TypeScript 工程化体系，对前端工程化、可观测性、微前端有深入理解。",
                meta={"tone": "professional"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="experience", title="工作经历",
                content_md="• 主导中后台统一门户重构，将 12 个分散系统整合为单页面架构，首屏加载从 4.2s 降至 1.1s\n• 设计并落地 30+ 通用业务组件，被 4 个 BU 复用，节省 35% 开发工时\n• 推进团队 TypeScript 覆盖率从 42% 提升至 96%",
                meta={"company": "某互联网大厂", "role": "高级前端工程师", "start": "2023-03"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="experience", title="",
                content_md="• 独立负责 BI 看板产品前端实现，支持 200+ 客户使用\n• 封装可视化图表库 18 种，渲染性能优化 60%\n• 推动 Cypress 自动化测试覆盖核心链路",
                meta={"company": "某 SaaS 创业公司", "role": "前端工程师", "start": "2021-07", "end": "2023-02"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="project", title="代表项目",
                content_md="自研基于 Web Components + Module Federation 的微前端框架 EdgeKit。支持独立部署、依赖共享、沙箱隔离，已在公司 6 个核心产品落地，体积较 qiankun 减少 40%。",
                meta={"name": "EdgeKit", "type": "微前端框架"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="skill", title="技能清单",
                content_md="React 18 · TypeScript · Vite · 微前端 · 可视化 · 性能优化 · Node.js · 设计系统",
                meta={"proficiency": "expert"},
            )
            await svc.create_block(
                main.id, user.id,
                block_type="education", title="教育背景",
                content_md="北京邮电大学 · 计算机科学与技术 · 本科\nGPA 3.7/4.0 · 校级优秀毕业生",
                meta={"school": "北京邮电大学", "major": "计算机科学与技术", "degree": "本科", "start": "2017-09", "end": "2021-06"},
            )
            await db.flush()
            print("seed: created 7 blocks on main branch")

            # 4. Create initial version for main branch
            v1 = await version_svc.create_manual_version(
                branch_id=main.id, user_id=user.id, label="初始化"
            )
            print(f"seed: created version v{v1.version_no}")

            # 5. Modify a block and create a second version
            blocks = await svc.list_blocks(main.id, user.id)
            if len(blocks) >= 3:
                await svc.patch_block(
                    blocks[2].id, user.id,
                    content_md="• 主导中后台统一门户重构，首屏加载从 4.2s 降至 1.1s（LCP 优化 73%）\n• 设计并落地 30+ 通用业务组件，被 4 个 BU 复用，节省 35% 开发工时\n• 推进团队 TypeScript 覆盖率从 42% 提升至 96%，建立 ESLint + Prettier 统一规范\n• 引入 Sentry + 自定义埋点，线上故障发现时间从 15min 降至 2min",
                )
            v2 = await version_svc.create_manual_version(
                branch_id=main.id, user_id=user.id, label="优化经历描述"
            )
            print(f"seed: created version v{v2.version_no}")
        else:
            print(f"seed: main branch {main.id} already exists, adding children")
            # Ensure main is ready
            await svc.patch_branch(main.id, user.id, status="ready")

        # 6. Create 4 child branches
        children_data = [
            {"name": "字节跳动 · 高级前端", "company": "字节跳动", "position": "高级前端工程师", "status": "optimizing", "match_score": 87.0, "is_pinned": True},
            {"name": "美团 · 高级前端", "company": "美团", "position": "高级前端工程师", "status": "ready", "match_score": 92.0, "is_pinned": False},
            {"name": "腾讯 · Web前端", "company": "腾讯", "position": "Web前端开发", "status": "ready", "match_score": 85.0, "is_pinned": False},
            {"name": "小红书 · 资深前端", "company": "小红书", "position": "资深前端工程师", "status": "draft", "match_score": 78.0, "is_pinned": False},
        ]

        for child_data in children_data:
            child = await svc.create_branch(
                user_id=user.id,
                name=child_data["name"],
                company=child_data["company"],
                position=child_data["position"],
                parent_id=main.id,
                is_main=False,
            )
            await svc.patch_branch(
                child.id, user.id,
                status=child_data["status"],
                is_pinned=child_data["is_pinned"],
            )
            # Set match_score directly (not in PATCH schema)
            child.match_score = child_data["match_score"]
            print(f"seed: created child branch {child.id} ({child_data['name']})")

        await db.commit()
        print(f"seed: done — user={user.id} main={main.id} children={len(children_data)} versions=2")


if __name__ == "__main__":
    asyncio.run(run())
