"""M032 — Resume v2 default data + template seeding (REB-032 v2 MVP stub).

The real implementation lives in feature 032 v2 US1 (T022 — defaults).
For the REB-032 v2 MVP we only need this module to import cleanly so
``app.modules.resumes_v2.service`` can call ``default_resume_data_v2()``
and ``apply_template(...)``. The full picture (template-specific seeding,
locale-aware defaults, sample resumes) ships in a later US phase.

The shape mirrors the frontend ``schema/defaults.ts`` exactly so the
backend can re-create the document when a POST arrives without a
``data`` payload.
"""
from __future__ import annotations

from typing import Any


def default_resume_data_v2() -> dict[str, Any]:
    """Return an empty-but-valid ResumeDataV2 document (matching the frontend Zod schema)."""
    return {
        "picture": {
            "hidden": True,
            "url": "",
            "size": 96,
            "rotation": 0,
            "aspectRatio": 1.0,
            "borderRadius": 0,
            "borderColor": "rgba(0, 0, 0, 1)",
            "borderWidth": 0,
            "shadowColor": "rgba(0, 0, 0, 0)",
            "shadowWidth": 0,
        },
        "basics": {
            "name": "",
            "headline": "",
            "email": "",
            "phone": "",
            "location": "",
            "website": {"url": "", "label": ""},
            "customFields": [],
        },
        "summary": {
            "title": "Summary",
            "icon": "user",
            "columns": 1,
            "hidden": False,
            "content": "",
        },
        "sections": {
            "profiles": {"title": "Profiles", "icon": "user", "columns": 1, "hidden": False, "items": []},
            "experience": {"title": "Experience", "icon": "briefcase", "columns": 1, "hidden": False, "items": []},
            "education": {"title": "Education", "icon": "graduation-cap", "columns": 1, "hidden": False, "items": []},
            "projects": {"title": "Projects", "icon": "folder", "columns": 1, "hidden": False, "items": []},
            "skills": {"title": "Skills", "icon": "wrench", "columns": 1, "hidden": False, "items": []},
            "languages": {"title": "Languages", "icon": "languages", "columns": 1, "hidden": False, "items": []},
            "interests": {"title": "Interests", "icon": "heart", "columns": 1, "hidden": False, "items": []},
            "awards": {"title": "Awards", "icon": "trophy", "columns": 1, "hidden": False, "items": []},
            "certifications": {"title": "Certifications", "icon": "badge-check", "columns": 1, "hidden": False, "items": []},
            "publications": {"title": "Publications", "icon": "book", "columns": 1, "hidden": False, "items": []},
            "volunteer": {"title": "Volunteer", "icon": "hand-heart", "columns": 1, "hidden": False, "items": []},
            "references": {"title": "References", "icon": "users", "columns": 1, "hidden": False, "items": []},
        },
        "customSections": [],
        "metadata": {
            "template": "onyx",
            "layout": {
                "sidebarWidth": 30,
                "pages": [
                    {
                        "fullWidth": False,
                        "main": [
                            "summary", "experience", "education", "projects",
                            "skills", "languages", "interests", "awards",
                            "certifications", "publications", "volunteer",
                            "references", "profiles",
                        ],
                        "sidebar": [],
                    }
                ],
            },
            "page": {
                "gapX": 16,
                "gapY": 16,
                "marginX": 32,
                "marginY": 32,
                "format": "a4",
                "locale": "zh-CN",
                "hideLinkUnderline": False,
                "hideIcons": False,
                "hideSectionIcons": False,
            },
            "design": {
                "level": {"icon": "circle", "type": "circle"},
                "colors": {
                    "primary": "rgba(0, 0, 0, 1)",
                    "text": "rgba(0, 0, 0, 1)",
                    "background": "rgba(255, 255, 255, 1)",
                },
            },
            "typography": {
                "body": {
                    "fontFamily": "Inter",
                    "fontWeights": ["400", "500", "700"],
                    "fontSize": 11,
                    "lineHeight": 1.5,
                },
                "heading": {
                    "fontFamily": "Inter",
                    "fontWeights": ["600", "700"],
                    "fontSize": 14,
                    "lineHeight": 1.3,
                },
            },
            "notes": "",
            "styleRules": [],
            "markdown": {
                "sourceMarkdown": "# 林溪 - AI 应用工程师\n\n## 个人总结\n\n5 年 AI 应用与全栈工程经验，专注 **RAG、Agent 工作流、企业知识库、评测体系**。\n",
                "themeId": "muji-default-autumn",
                "manualLineHeight": 19,
                "smartOnePageEnabled": False,
                "smartLineHeight": None,
                "previousManualLineHeight": None,
                "smartStatus": "idle",
            },
        },
    }


def apply_template(data: dict[str, Any], template: str) -> dict[str, Any]:
    """Mutate ``data`` in place so its ``metadata.template`` matches ``template``.

    For the MVP we only set the template id; full per-template seeding
    (color overrides, layout defaults, sample sections) lands in a later
    US phase. Unknown template ids fall back to ``"onyx"`` to match the
    frontend's REB-034 fallback behavior.
    """
    valid = {
        "onyx", "azurill", "kakuna", "chikorita", "ditgar",
        "bronzor", "pikachu", "lapras", "scizor", "rhyhorn",
    }
    effective = template if template in valid else "onyx"
    metadata = data.setdefault("metadata", {})
    metadata["template"] = effective
    return data
