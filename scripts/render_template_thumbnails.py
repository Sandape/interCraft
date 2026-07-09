# -*- coding: utf-8 -*-
"""T046 - Render 10 template thumbnails to JPGs.

Walks each of the 10 v2 templates, renders them with sample data
into an HTML document, and screenshots the result at 400x565 px
(A4-ish aspect ratio). Saves the result to
`public/templates/jpg/<id>.jpg`.

Why Python (not Node)?
- eGGG's existing `pdf_renderer` already uses Playwright Python
  (chromium launched via `p.chromium.launch()`). Reusing the same runtime
  keeps the browser binary in one place and avoids pulling in
  `playwright` for Node.
- We don't need to spin up a real backend — we just need a one-off
  Chromium instance to render self-contained HTML.

Usage:
    cd D:\Project\eGGG
    python scripts/render_template_thumbnails.py

Pre-req: `playwright install chromium` (already done for the PDF renderer).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JPG_DIR = PROJECT_ROOT / "public" / "templates" / "jpg"
TEMPLATES_DIR = PROJECT_ROOT / "src" / "modules" / "resume" / "v2" / "templates"
TEMPLATE_IDS = [
    "onyx",
    "azurill",
    "kakuna",
    "chikorita",
    "ditgar",
    "bronzor",
    "pikachu",
    "lapras",
    "scizor",
    "rhyhorn",
]


def read_css_for(template_id: str) -> str:
    """Read template.css for a given template (root + nested)."""
    css_parts: list[str] = []
    shared_css = TEMPLATES_DIR / "shared" / "template.css"
    if shared_css.exists():
        css_parts.append(shared_css.read_text(encoding="utf-8"))
    css_path = TEMPLATES_DIR / template_id / "template.css"
    if css_path.exists():
        css_parts.append(css_path.read_text(encoding="utf-8"))
    return "\n\n".join(css_parts)


def build_sample_data() -> dict:
    """Return a sample ResumeDataV2 dict for thumbnail rendering.

    Mirrors `src/modules/resume/v2/schema/defaults.ts` but with sample
    content (name, headline, a few experience items) so the rendered
    thumbnail is visually informative instead of a blank page.
    """
    return {
        "picture": {
            "hidden": False,
            "url": "",
            "size": 80,
            "rotation": 0,
            "aspectRatio": 1,
            "borderRadius": 0,
            "borderColor": "rgba(0, 0, 0, 0.5)",
            "borderWidth": 0,
            "shadowColor": "rgba(0, 0, 0, 0.5)",
            "shadowWidth": 0,
        },
        "basics": {
            "name": "Alex Morgan",
            "headline": "Senior Software Engineer | Distributed Systems",
            "email": "alex@example.com",
            "phone": "+1 (555) 123-4567",
            "location": "Seattle, WA",
            "website": {"url": "https://alexmorgan.dev", "label": "alexmorgan.dev"},
            "customFields": [],
        },
        "summary": {
            "title": "个人简介",
            "icon": "file-text",
            "columns": 1,
            "hidden": False,
            "content": (
                "<p>Senior software engineer with 8+ years of experience building "
                "distributed systems at scale. Specialised in Go, Rust, and Kubernetes "
                "internals. Proven track record of leading teams, mentoring engineers, "
                "and shipping reliable production services.</p>"
            ),
        },
        "sections": {
            "profiles": {
                "title": "社交账号",
                "icon": "link",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "p-1",
                        "hidden": False,
                        "icon": "github",
                        "iconColor": "rgba(0, 0, 0, 0)",
                        "network": "GitHub",
                        "username": "alexmorgan",
                        "website": {
                            "url": "https://github.com/alexmorgan",
                            "label": "github.com/alexmorgan",
                            "inlineLink": False,
                        },
                    }
                ],
            },
            "experience": {
                "title": "工作经历",
                "icon": "briefcase",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "e-1",
                        "hidden": False,
                        "company": "Acme Cloud",
                        "position": "Senior Software Engineer",
                        "location": "Remote",
                        "period": "2022 – Present",
                        "website": {"url": "", "label": "", "inlineLink": False},
                        "description": (
                            "<p>Led migration of core services to multi-region "
                            "active-active topology. Reduced p99 latency by 35%.</p>"
                        ),
                        "roles": [],
                    },
                    {
                        "id": "e-2",
                        "hidden": False,
                        "company": "BetaSoft",
                        "position": "Software Engineer",
                        "location": "Seattle, WA",
                        "period": "2018 – 2022",
                        "website": {"url": "", "label": "", "inlineLink": False},
                        "description": (
                            "<p>Built distributed tracing pipeline processing 5B "
                            "spans/day. Mentored 4 junior engineers.</p>"
                        ),
                        "roles": [],
                    },
                ],
            },
            "education": {
                "title": "教育经历",
                "icon": "graduation-cap",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "ed-1",
                        "hidden": False,
                        "school": "University of Washington",
                        "degree": "B.S.",
                        "area": "Computer Science",
                        "grade": "3.9/4.0",
                        "location": "Seattle, WA",
                        "period": "2014 – 2018",
                        "website": {"url": "", "label": "", "inlineLink": False},
                        "description": "",
                    }
                ],
            },
            "projects": {
                "title": "项目经验",
                "icon": "code",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "pr-1",
                        "hidden": False,
                        "name": "OpenTelemetry Rust SDK",
                        "period": "2021 – Present",
                        "website": {"url": "", "label": "", "inlineLink": False},
                        "description": (
                            "<p>Core maintainer. Implemented batch span processor "
                            "with adaptive sampling.</p>"
                        ),
                    }
                ],
            },
            "skills": {
                "title": "技能",
                "icon": "wrench",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "s-1",
                        "hidden": False,
                        "icon": "wrench",
                        "iconColor": "rgba(0, 0, 0, 0)",
                        "name": "Backend",
                        "proficiency": "Expert",
                        "level": 5,
                        "keywords": ["Go", "Rust", "Python"],
                    },
                    {
                        "id": "s-2",
                        "hidden": False,
                        "icon": "wrench",
                        "iconColor": "rgba(0, 0, 0, 0)",
                        "name": "Infrastructure",
                        "proficiency": "Expert",
                        "level": 5,
                        "keywords": ["Kubernetes", "Terraform", "AWS"],
                    },
                ],
            },
            "languages": {
                "title": "语言能力",
                "icon": "languages",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "l-1",
                        "hidden": False,
                        "language": "English",
                        "fluency": "Native",
                        "level": 5,
                    },
                    {
                        "id": "l-2",
                        "hidden": False,
                        "language": "Mandarin",
                        "fluency": "Professional",
                        "level": 4,
                    },
                ],
            },
            "interests": {
                "title": "兴趣爱好",
                "icon": "heart",
                "columns": 1,
                "hidden": False,
                "items": [
                    {
                        "id": "i-1",
                        "hidden": False,
                        "icon": "heart",
                        "iconColor": "rgba(0, 0, 0, 0)",
                        "name": "Open source",
                        "keywords": ["Kubernetes", "Rust"],
                    }
                ],
            },
            "awards": {
                "title": "荣誉奖项",
                "icon": "trophy",
                "columns": 1,
                "hidden": False,
                "items": [],
            },
            "certifications": {
                "title": "认证",
                "icon": "award",
                "columns": 1,
                "hidden": False,
                "items": [],
            },
            "publications": {
                "title": "出版",
                "icon": "book-open",
                "columns": 1,
                "hidden": False,
                "items": [],
            },
            "volunteer": {
                "title": "志愿服务",
                "icon": "hand-heart",
                "columns": 1,
                "hidden": False,
                "items": [],
            },
            "references": {
                "title": "推荐人",
                "icon": "phone",
                "columns": 1,
                "hidden": False,
                "items": [],
            },
        },
        "customSections": [],
        "metadata": {
            "template": "pikachu",
            "layout": {
                "sidebarWidth": 35,
                "pages": [
                    {
                        "fullWidth": False,
                        "main": ["summary", "experience", "education", "projects"],
                        "sidebar": ["profiles", "skills", "languages", "interests"],
                    }
                ],
            },
            "page": {
                "gapX": 4,
                "gapY": 6,
                "marginX": 14,
                "marginY": 12,
                "format": "a4",
                "locale": "zh-CN",
                "hideLinkUnderline": False,
                "hideIcons": False,
                "hideSectionIcons": True,
            },
            "design": {
                "colors": {
                    "primary": "rgba(0, 132, 209, 1)",
                    "text": "rgba(0, 0, 0, 1)",
                    "background": "rgba(255, 255, 255, 1)",
                },
                "level": {"icon": "star", "type": "circle"},
            },
            "typography": {
                "body": {
                    "fontFamily": "IBM Plex Sans",
                    "fontWeights": ["400"],
                    "fontSize": 10,
                    "lineHeight": 1.5,
                },
                "heading": {
                    "fontFamily": "IBM Plex Sans",
                    "fontWeights": ["600"],
                    "fontSize": 14,
                    "lineHeight": 1.5,
                },
            },
            "notes": "",
            "styleRules": [],
        },
    }


def build_html(template_id: str, css: str, primary: str) -> str:
    """Render the template's HTML body fragment for screenshotting.

    The script does not run React; it embeds a self-contained HTML
    that mirrors what each template would render with sample data.
    The visual identity for the thumbnail is approximated by applying
    the template's CSS and stamping the primary color into a header
    band for templates that have one (Pikachu, Lapras, Scizor, etc.).
    """
    data = build_sample_data()
    # Adjust primary color per template (matches manifest.json recommendedColors).
    data["metadata"]["design"]["colors"]["primary"] = primary
    data["metadata"]["template"] = template_id

    summary = data["summary"]["content"]
    name = data["basics"]["name"]
    headline = data["basics"]["headline"]
    contact = " · ".join(
        x
        for x in [
            data["basics"]["email"],
            data["basics"]["phone"],
            data["basics"]["location"],
        ]
        if x
    )

    # Experience block (3 items max for thumbnail)
    exp_html = "".join(
        f"<div class='rs-tpl__item'><div class='rs-tpl__item-head'>"
        f"<span class='rs-tpl__item-title'>{item['position']}</span>"
        f"<span class='rs-tpl__item-org'> @ {item['company']}</span>"
        f"<span class='rs-tpl__item-period'> · {item['period']}</span>"
        f"</div><div class='rs-tpl__item-meta'>{item['location']}</div></div>"
        for item in data["sections"]["experience"]["items"]
    )
    skills_html = "".join(
        f"<li class='rs-tpl__item rs-tpl__skill-item'>"
        f"<span class='rs-tpl__skill-name'>{s['name']}</span> "
        f"<span class='rs-tpl__skill-keywords'>{', '.join(s['keywords'])}</span>"
        f"</li>"
        for s in data["sections"]["skills"]["items"]
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{template_id} thumbnail</title>
<style>
{css}
/* Thumbnail-specific overrides: collapse the resume to a 400x565 viewport. */
.rs-tpl-root {{
  width: 400px;
  height: 565px;
  overflow: hidden;
  font-size: 8pt;
  padding: 12pt;
}}
</style>
</head>
<body>
<div data-template="{template_id}" data-rs-tpl class="rs-tpl-root rs-tpl--{template_id}">
<header class="rs-tpl__header" data-header>
  <div class="rs-tpl__header-text">
    <h1 class="rs-tpl__name">{name}</h1>
    <div class="rs-tpl__headline">{headline}</div>
    <div class="rs-tpl__contact-list" data-contact-list>{contact}</div>
  </div>
</header>
<section data-section-id="summary" data-section="summary" class="rs-tpl__section">
  <h2 class="rs-tpl__section-heading" data-heading>个人简介</h2>
  <div class="rs-tpl__rich rs-tpl__summary">{summary}</div>
</section>
<section data-section-id="experience" data-section="experience" class="rs-tpl__section">
  <h2 class="rs-tpl__section-heading" data-heading>工作经历</h2>
  {exp_html}
</section>
<section data-section-id="skills" data-section="skills" class="rs-tpl__section">
  <h2 class="rs-tpl__section-heading" data-heading>技能</h2>
  <ul class="rs-tpl__list rs-tpl__skills">{skills_html}</ul>
</section>
</div>
</body>
</html>
"""


PRIMARY_BY_TEMPLATE = {
    "onyx": "rgba(0, 132, 209, 1)",
    "azurill": "rgba(0, 132, 209, 1)",
    "kakuna": "rgba(75, 85, 99, 1)",
    "chikorita": "rgba(34, 197, 94, 1)",
    "ditgar": "rgba(15, 23, 42, 1)",
    "bronzor": "rgba(120, 53, 15, 1)",
    "pikachu": "rgba(255, 200, 55, 1)",
    "lapras": "rgba(99, 102, 241, 1)",
    "scizor": "rgba(220, 38, 38, 1)",
    "rhyhorn": "rgba(30, 58, 138, 1)",
}


async def render_one(page, template_id: str) -> Path:
    css = read_css_for(template_id)
    primary = PRIMARY_BY_TEMPLATE.get(template_id, "rgba(0, 132, 209, 1)")
    html = build_html(template_id, css, primary)
    await page.set_viewport_size({"width": 400, "height": 565})
    await page.set_content(html, wait_until="load")
    out_path = JPG_DIR / f"{template_id}.jpg"
    JPG_DIR.mkdir(parents=True, exist_ok=True)
    # Screenshot just the .rs-tpl-root element for tight crop.
    locator = page.locator(".rs-tpl-root")
    await locator.screenshot(path=str(out_path), type="jpeg", quality=85)
    return out_path


async def main() -> int:
    JPG_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 400, "height": 565},
            device_scale_factor=2,
        )
        page = await context.new_page()
        for template_id in TEMPLATE_IDS:
            try:
                out = await render_one(page, template_id)
                size = out.stat().st_size
                print(f"  [{template_id}] -> {out.relative_to(PROJECT_ROOT)} ({size} bytes)")
            except Exception as exc:  # noqa: BLE001
                print(f"  [{template_id}] FAILED: {exc}", file=sys.stderr)
        await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
