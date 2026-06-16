"""PDF generation service for ability profile exports.

Uses playwright-python to render profile HTML → page.pdf().
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

PDF_EXPORT_DIR = os.environ.get(
    "PDF_EXPORT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "exports"),
)


async def generate_profile_pdf(user_id: UUID) -> str:
    """Generate a PDF for the given user's profile.

    Returns the file path of the generated PDF.
    """
    os.makedirs(PDF_EXPORT_DIR, exist_ok=True)
    filename = f"ability-profile-{user_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    filepath = os.path.join(PDF_EXPORT_DIR, filename)

    from playwright.async_api import async_playwright

    # Build a simple HTML page with the profile data
    html = await _build_profile_html(user_id)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=filepath, format="A4", print_background=True)
        await browser.close()

    logger.info("pdf_export.generated", extra={"user_id": str(user_id), "path": filepath})
    return filepath


async def _build_profile_html(user_id: UUID) -> str:
    """Build an HTML string with profile data for PDF rendering.

    Uses inline styles to avoid external dependencies.
    """
    from app.core.db import get_session_factory
    from app.modules.ability_profile.repository import AbilityProfileRepository
    from app.modules.ability_profile.service import AbilityProfileService, DIMENSION_LABELS

    factory = get_session_factory()
    async with factory() as session:
        repo = AbilityProfileRepository(session)
        svc = AbilityProfileService(repo, session)
        dashboard = await svc.get_dashboard(user_id)
        owner = await svc._fetch_user_info(user_id)

    dims = dashboard.get("dimensions", [])
    dim_rows = "\n".join(
        f"""<tr>
            <td>{d.get("label_zh", d["key"])}</td>
            <td>{d.get("actual_score", 0)}</td>
            <td>{d.get("ideal_score", 10)}</td>
            <td>{d.get("trend", "stable")}</td>
        </tr>"""
        for d in dims
    )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    name = owner.get("name", "Unknown")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
    body {{ font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif; padding: 40px; color: #333; }}
    h1 {{ color: #1a1a2e; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
    th {{ background-color: #f5f5f5; font-weight: 600; }}
    .footer {{ margin-top: 40px; color: #888; font-size: 12px; text-align: center; }}
    .score {{ font-weight: bold; color: #2563eb; }}
</style>
</head>
<body>
    <h1>能力画像报告</h1>
    <p>姓名: {name}</p>
    <p>生成时间: {now_str}</p>
    <table>
        <thead>
            <tr><th>能力维度</th><th>当前分数</th><th>目标分数</th><th>趋势</th></tr>
        </thead>
        <tbody>
            {dim_rows}
        </tbody>
    </table>
    <div class="footer">InterCraft — 能力画像模块</div>
</body>
</html>"""


__all__ = ["generate_profile_pdf"]
