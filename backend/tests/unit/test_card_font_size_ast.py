"""[REQ-048 US4 AC-21] Unit test for AST font-size static checker.

Validates AC-21 (R13 + R21):
- The checker reads .tsx templates and asserts inline ``fontSize``
  attributes meet min_inline (64) for titles and min_body (24) for body.
- 4 indirect font-size paths are covered:
    1. inline ``style={{ fontSize: N }}`` — direct numeric
    2. ``className`` — fail closed
    3. ``style={{ fontSize: 'var(--title-size)' }}`` — fail closed
    4. ``<h1>`` / ``<h2>`` / ``<h3>`` default sizes — fail closed
      unless inline override is present
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.card_renderer.ast_check_card_font_size import (
    H1_DEFAULT_PX,
    H2_DEFAULT_PX,
    check,
    check_file,
)


TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "app/services/card_renderer/templates"


def _write_tmp_template(tmp_path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ----- Happy path: actual templates pass ----


def test_real_card_4x3_template_passes_all_4_paths(tmp_path) -> None:
    """The shipped card_4x3.tsx template must pass all 4 AC-21 paths."""
    src = TEMPLATES_DIR / "card_4x3.tsx"
    if not src.exists():
        pytest.skip("card_4x3.tsx not present yet")
    result = check_file(
        src,
        check_inline_style=True,
        check_h1_default=True,
        check_css_variable=True,
        check_classname=True,
        min_inline=64,
        min_body=24,
    )
    assert result.passed, f"template failed AC-21: {result.issues}"


def test_real_card_9x16_template_passes_all_4_paths(tmp_path) -> None:
    """The shipped card_9x16.tsx template must pass all 4 AC-21 paths."""
    src = TEMPLATES_DIR / "card_9x16.tsx"
    if not src.exists():
        pytest.skip("card_9x16.tsx not present yet")
    result = check_file(
        src,
        check_inline_style=True,
        check_h1_default=True,
        check_css_variable=True,
        check_classname=True,
        min_inline=64,
        min_body=24,
    )
    assert result.passed, f"template failed AC-21: {result.issues}"


def test_real_card_templates_pass_via_check_function() -> None:
    results = check(
        [str(TEMPLATES_DIR / "card_4x3.tsx"), str(TEMPLATES_DIR / "card_9x16.tsx")],
        check_inline_style=True,
        check_h1_default=True,
        check_css_variable=True,
        check_classname=True,
        min_inline=64,
    )
    for r in results:
        assert r.passed, f"{r.template}: {r.issues}"


# ----- 4 indirect paths: failing cases ----


def test_path1_inline_below_min_inline_fails(tmp_path) -> None:
    p = _write_tmp_template(
        tmp_path,
        "card_bad.tsx",
        """
        export default function Card() {
          return <svg><text fontSize={20}>title too small</text></svg>;
        }
        """,
    )
    result = check_file(
        p,
        check_inline_style=True,
        check_h1_default=False,
        check_css_variable=False,
        check_classname=False,
        min_inline=64,
    )
    assert result.passed is False
    assert any("max inline fontSize" in i for i in result.issues)


def test_path2_classname_fails_closed(tmp_path) -> None:
    p = _write_tmp_template(
        tmp_path,
        "card_classname.tsx",
        """
        export default function Card() {
          return <svg><text className="title-h1">Classname size</text></svg>;
        }
        """,
    )
    result = check_file(
        p,
        check_inline_style=False,
        check_h1_default=False,
        check_css_variable=False,
        check_classname=True,
        min_inline=64,
    )
    assert result.passed is False
    assert any("className" in i for i in result.issues)
    assert result.classname_count >= 1


def test_path3_css_variable_fails_closed(tmp_path) -> None:
    p = _write_tmp_template(
        tmp_path,
        "card_cssvar.tsx",
        """
        export default function Card() {
          return (
            <svg>
              <text style={{ fontSize: 'var(--title-size)' }}>CSS var size</text>
            </svg>
          );
        }
        """,
    )
    result = check_file(
        p,
        check_inline_style=False,
        check_h1_default=False,
        check_css_variable=True,
        check_classname=False,
        min_inline=64,
    )
    assert result.passed is False
    assert any("CSS variable" in i for i in result.issues)
    assert result.css_variable_count >= 1


def test_path4_h1_default_fails_without_inline_override(tmp_path) -> None:
    p = _write_tmp_template(
        tmp_path,
        "card_h1.tsx",
        """
        export default function Card() {
          return (
            <svg>
              <h1 style={{ fontSize: 32 }}>Title default</h1>
            </svg>
          );
        }
        """,
    )
    result = check_file(
        p,
        check_inline_style=True,
        check_h1_default=True,
        check_css_variable=False,
        check_classname=False,
        min_inline=64,
    )
    # h1 is present but max inline is only 32 < 64 → fail.
    assert result.passed is False
    assert any("<h1>" in i for i in result.issues)
    assert result.h1_count == 1


def test_path4_h1_passes_with_inline_override(tmp_path) -> None:
    p = _write_tmp_template(
        tmp_path,
        "card_h1_ok.tsx",
        """
        export default function Card() {
          return (
            <svg>
              <h1 style={{ fontSize: 80 }}>Title with inline</h1>
            </svg>
          );
        }
        """,
    )
    result = check_file(
        p,
        check_inline_style=True,
        check_h1_default=True,
        check_css_variable=False,
        check_classname=False,
        min_inline=64,
    )
    assert result.passed is True
    assert result.max_inline == 80


# ----- Defaults & edge cases ----


def test_missing_template_marks_failed(tmp_path) -> None:
    """Missing template file is reported as a failure (CI friendly)."""
    p = tmp_path / "nope.tsx"
    result = check_file(p)
    assert result.passed is False
    assert any("template not found" in i for i in result.issues)


def test_h1_h2_h3_default_constants() -> None:
    assert H1_DEFAULT_PX == 32
    assert H2_DEFAULT_PX == 24


def test_min_inline_default_is_64() -> None:
    p = _write_tmp_template(
        tmp_path := __import__("pathlib").Path(),
        "x.tsx",
        "",
    )
    # 64 is AC-21's locked minimum for titles.
    import inspect

    sig = inspect.signature(check_file)
    assert sig.parameters["min_inline"].default == 64


def test_check_function_returns_list_of_results(tmp_path) -> None:
    p1 = _write_tmp_template(tmp_path, "a.tsx", "")
    p2 = _write_tmp_template(tmp_path, "b.tsx", "")
    results = check([p1, p2], min_inline=64)
    assert len(results) == 2
    assert all(r.template.endswith(".tsx") for r in results)