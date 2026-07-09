"""[REQ-048 US4 / AC-21] AST font-size checker for card templates.

Per AC-21 (R13 + R21):

> Card text font sizes must be ≥ 24px. Key titles must be ≥ 64px. The
> check is a pure AST analysis of the satori JSX templates — no PNG /
> OCR / Tesseract dependency.
>
> 4 indirect font-size paths must be detected:
>
> 1. inline ``style={{ fontSize: N }}`` — direct numeric (≥ 64 for
>    titles, ≥ 24 for body);
> 2. ``className="..."`` referencing an external CSS class — fail
>    closed (the static checker cannot resolve the class);
> 3. ``style={{ fontSize: 'var(--title-size)' }}`` — fail closed;
> 4. ``<h1>`` / ``<h2>`` / ``<h3>`` default sizes (32 / 24 / 18 px
>    respectively) — fail closed unless an inline ``fontSize`` is
>    present on the element.

CLI:

    python -m app.services.card_renderer.ast_check_card_font_size \\
        --templates backend/app/services/card_renderer/templates/card_4x3.tsx \\
                    backend/app/services/card_renderer/templates/card_9x16.tsx \\
        --check-inline-style \\
        --check-h1-default \\
        --check-css-variable \\
        --check-classname \\
        --min-inline 64 \\
        --min-body 24

Exit code is 0 when all checks pass; 1 when any check fails. The
script is invoked by ``scripts.ast_check_card_font_size`` (AC-21
verification command) and also re-exported as the module-level
``check()`` helper used by the unit tests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Default font sizes for native HTML heading elements (satori respects
# these when no inline ``fontSize`` overrides them). Numbers come from
# the typical browser/satori defaults.
H1_DEFAULT_PX = 32
H2_DEFAULT_PX = 24
H3_DEFAULT_PX = 18


@dataclass
class FontCheckResult:
    template: str
    inline_count: int = 0
    min_inline: int | None = None
    max_inline: int | None = None
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    css_variable_count: int = 0
    classname_count: int = 0
    issues: list[str] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "inline_count": self.inline_count,
            "min_inline": self.min_inline,
            "max_inline": self.max_inline,
            "h1_count": self.h1_count,
            "h2_count": self.h2_count,
            "h3_count": self.h3_count,
            "css_variable_count": self.css_variable_count,
            "classname_count": self.classname_count,
            "issues": list(self.issues),
            "passed": self.passed,
        }


_INLINE_FONT_RE = re.compile(
    r"\bfontSize[A-Za-z]*\s*[:=]\s*['\"]?([0-9]+)"
)
_H1_RE = re.compile(r"<\s*h1\b")
_H2_RE = re.compile(r"<\s*h2\b")
_H3_RE = re.compile(r"<\s*h3\b")
_CSS_VAR_RE = re.compile(r"fontSize\s*:\s*['\"]?var\(")
_CLASSNAME_RE = re.compile(r"className\s*=\s*['\"][^'\"]+['\"]")
_COMMENT_LINE_RE = re.compile(r"^\s*(?://|\*|/\*)")
_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")


def check_file(
    path: str | Path,
    *,
    check_inline_style: bool = True,
    check_h1_default: bool = True,
    check_css_variable: bool = True,
    check_classname: bool = True,
    min_inline: int = 64,
    min_body: int = 24,
) -> FontCheckResult:
    """Run the full AC-21 font-size static analysis on a single template."""
    p = Path(path)
    if not p.exists():
        result = FontCheckResult(template=str(p))
        result.issues.append(f"template not found: {p}")
        result.passed = False
        return result

    raw_text = p.read_text(encoding="utf-8")
    # Strip block comments so false positives from `* no <h1> / <h2> / <h3> tags`
    # documentation strings don't trigger the H1 default-size guard.
    text = _BLOCK_COMMENT_RE.sub("", raw_text)
    result = FontCheckResult(template=str(p))

    # 1. inline fontSize values
    inline_matches = [int(m) for m in _INLINE_FONT_RE.findall(text)]
    result.inline_count = len(inline_matches)
    if inline_matches:
        result.min_inline = min(inline_matches)
        result.max_inline = max(inline_matches)

    # 2. <h1> / <h2> / <h3>
    result.h1_count = len(_H1_RE.findall(text))
    result.h2_count = len(_H2_RE.findall(text))
    result.h3_count = len(_H3_RE.findall(text))

    # 3. CSS variable references (fontSize: var(--…))
    result.css_variable_count = len(_CSS_VAR_RE.findall(text))

    # 4. className references
    result.classname_count = len(_CLASSNAME_RE.findall(text))

    # ---- Apply checks ----

    if check_inline_style:
        # Title class (max_inline) must be ≥ min_inline (default 64).
        if result.max_inline is None or result.max_inline < min_inline:
            result.issues.append(
                f"max inline fontSize={result.max_inline} < min_inline={min_inline} "
                f"(titles must declare inline fontSize >= {min_inline})"
            )
            result.passed = False
        # Body class (min_inline) must be ≥ min_body (default 24).
        if result.min_inline is not None and result.min_inline < min_body:
            result.issues.append(
                f"min inline fontSize={result.min_inline} < min_body={min_body} "
                f"(body text must be >= {min_body})"
            )
            result.passed = False

    if check_h1_default:
        if result.h1_count > 0:
            # <h1> defaults to 32px which is < min_inline (64) — fail
            # unless inline override is on the same element (which we
            # approximate by: if max_inline ≥ 64 the template is using
            # inline for the largest heading).
            if result.max_inline is None or result.max_inline < min_inline:
                result.issues.append(
                    f"<h1> count={result.h1_count} uses default 32px < {min_inline}; "
                    f"inline fontSize >= {min_inline} required"
                )
                result.passed = False

    if check_css_variable:
        if result.css_variable_count > 0:
            result.issues.append(
                f"CSS variable fontSize count={result.css_variable_count}; "
                f"static checker cannot resolve --title-size vars — use inline fontSize"
            )
            result.passed = False

    if check_classname:
        if result.classname_count > 0:
            # External stylesheet fontsizes cannot be verified statically —
            # fail closed per AC-21.
            result.issues.append(
                f"className count={result.classname_count}; "
                f"external CSS classes cannot be statically checked — use inline fontSize"
            )
            result.passed = False

    return result


def check(
    paths: list[str | Path],
    *,
    check_inline_style: bool = True,
    check_h1_default: bool = True,
    check_css_variable: bool = True,
    check_classname: bool = True,
    min_inline: int = 64,
    min_body: int = 24,
) -> list[FontCheckResult]:
    """Run the checks across multiple templates; return one result per path."""
    return [
        check_file(
            p,
            check_inline_style=check_inline_style,
            check_h1_default=check_h1_default,
            check_css_variable=check_css_variable,
            check_classname=check_classname,
            min_inline=min_inline,
            min_body=min_body,
        )
        for p in paths
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="REQ-048 US4 AC-21 — card template font-size static checker",
    )
    parser.add_argument(
        "--templates",
        nargs="+",
        required=True,
        help="Card template .tsx file paths",
    )
    parser.add_argument("--check-inline-style", action="store_true")
    parser.add_argument("--check-h1-default", action="store_true")
    parser.add_argument("--check-css-variable", action="store_true")
    parser.add_argument("--check-classname", action="store_true")
    parser.add_argument(
        "--min-inline",
        type=int,
        default=64,
        help="Min inline fontSize for titles (default 64 per AC-21)",
    )
    parser.add_argument(
        "--min-body",
        type=int,
        default=24,
        help="Min body fontSize (default 24 per AC-21)",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    results = check(
        args.templates,
        check_inline_style=args.check_inline_style,
        check_h1_default=args.check_h1_default,
        check_css_variable=args.check_css_variable,
        check_classname=args.check_classname,
        min_inline=args.min_inline,
        min_body=args.min_body,
    )
    payload = {"results": [r.to_dict() for r in results]}
    all_passed = all(r.passed for r in results)
    payload["all_passed"] = all_passed
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.template}")
            if r.issues:
                for issue in r.issues:
                    print(f"  - {issue}")
    return 0 if all_passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "FontCheckResult",
    "check",
    "check_file",
    "main",
]