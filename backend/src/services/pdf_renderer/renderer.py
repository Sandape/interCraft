"""Puppeteer-based resume renderer — renders Markdown + style to PDF/PNG/JPEG."""

import os
import logging
from pathlib import Path

logger = logging.getLogger("pdf-renderer")

_STYLES_DIR = Path(__file__).parent / "styles"
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_css(style_id: str) -> str:
    path = _STYLES_DIR / f"{style_id}.css"
    if not path.exists():
        raise FileNotFoundError(f"CSS not found for style '{style_id}': {path}")
    return path.read_text(encoding="utf-8")


def _load_template(style_id: str) -> str:
    path = _TEMPLATES_DIR / f"{style_id}.html"
    if not path.exists():
        raise FileNotFoundError(f"Template not found for style '{style_id}': {path}")
    return path.read_text(encoding="utf-8")


def _markdown_to_html(markdown: str) -> str:
    import re

    lines = markdown.strip().split("\n")
    html_parts: list[str] = []
    in_list = False
    in_frontmatter = False
    frontmatter: dict[str, str] = {}

    def close_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Frontmatter
        if line.strip() == "---" and not in_frontmatter and i == 0:
            in_frontmatter = True
            i += 1
            continue
        if line.strip() == "---" and in_frontmatter:
            in_frontmatter = False
            i += 1
            continue
        if in_frontmatter:
            if ":" in line:
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip()
            i += 1
            continue

        # H1
        if line.startswith("# ") and not line.startswith("## "):
            close_list()
            html_parts.append(f'<h1 class="resume-name">{_escape(line[2:].strip())}</h1>')
            i += 1
            # Next line might be contact info
            if i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
                contact = lines[i].strip()
                html_parts.append(f'<p class="resume-contact">{_escape(contact)}</p>')
                i += 1
            continue

        # H2
        if line.startswith("## "):
            close_list()
            heading = line[3:].strip()
            # Parse section title — optionally with meta after "—"
            parts = heading.split("—")
            section_title = parts[0].strip()
            meta_text = parts[1].strip() if len(parts) > 1 else ""
            html_parts.append('<div class="resume-section">')
            html_parts.append(f"<h2>{_escape(section_title)}</h2>")
            if meta_text:
                html_parts.append(f'<p class="meta-line">{_escape(meta_text)}</p>')
            i += 1

            # Frontmatter right after heading
            if i < len(lines) and lines[i].strip() == "---":
                i += 1
                block_meta: dict[str, str] = {}
                while i < len(lines) and lines[i].strip() != "---":
                    fline = lines[i]
                    if ":" in fline:
                        k, v = fline.split(":", 1)
                        block_meta[k.strip()] = v.strip()
                    i += 1
                if i < len(lines):
                    i += 1  # closing ---
                if block_meta:
                    meta_company = block_meta.get("company", "")
                    meta_role = block_meta.get("role", "")
                    meta_duration = block_meta.get("duration", "")
                    meta_str = " · ".join(filter(None, [meta_company, meta_role, meta_duration]))
                    if meta_str:
                        html_parts.append(f'<p class="meta-line">{_escape(meta_str)}</p>')

            # Process content until next H2
            while i < len(lines) and not lines[i].startswith("## "):
                cline = lines[i]
                stripped = cline.strip()
                if stripped:
                    if stripped.startswith("- "):
                        if not in_list:
                            html_parts.append("<ul>")
                            in_list = True
                        html_parts.append(f"<li>{_escape(stripped[2:].strip())}</li>")
                    else:
                        close_list()
                        # Bold: **text**
                        text = _escape(stripped)
                        text = text.replace("**", "<strong>", 1)
                        while "**" in text:
                            text = text.replace("**", "</strong>", 1)
                            if "**" in text:
                                text = text.replace("**", "<strong>", 1)
                        html_parts.append(f"<p>{text}</p>")
                else:
                    close_list()
                i += 1
            close_list()
            html_parts.append("</div>")
            continue

        # Empty lines
        if not line.strip():
            close_list()
            i += 1
            continue

        # Regular paragraph
        close_list()
        html_parts.append(f"<p>{_escape(line.strip())}</p>")
        i += 1

    close_list()
    return "\n".join(html_parts)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


async def render_resume(markdown: str, style_id: str, format_type: str) -> bytes:
    """Render a resume to PDF, PNG, or JPEG using a local headless browser."""

    css = _load_css(style_id)
    try:
        template_html = _load_template(style_id)
    except FileNotFoundError:
        template_html = _load_template("classic-one-page")

    # Build body HTML from markdown
    body_html = _markdown_to_html(markdown)

    # Inject CSS and body into template
    html = template_html.replace("{{STYLE_CSS}}", css).replace("{{BODY}}", body_html)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: playwright install chromium")
        raise RuntimeError("Playwright not available")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 794, "height": 1123})
        await page.set_content(html, wait_until="networkidle")

        if format_type == "pdf":
            result = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        else:
            result = await page.screenshot(
                full_page=True,
                type=format_type,
                scale="device",
            )

        await browser.close()
        return result
