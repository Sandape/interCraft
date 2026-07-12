from app.modules.resumes_v2.defaults import apply_creation_preferences, default_resume_data_v2
from app.modules.resumes_v2.schemas import ResumeV2CreateIn


def test_create_schema_accepts_editor_theme_ids_without_removing_legacy_template():
    payload = ResumeV2CreateIn(
        name="产品经理简历",
        slug="pm-resume",
        template="onyx",
        theme_id="muji-minimal-color",
    )

    assert payload.template == "onyx"
    assert payload.theme_id == "muji-minimal-color"


def test_normal_creation_uses_neutral_markdown_and_selected_theme():
    data = apply_creation_preferences(
        default_resume_data_v2(),
        theme_id="muji-flat-atmospheric",
        from_sample=False,
    )

    markdown = data["metadata"]["markdown"]
    assert markdown["themeId"] == "muji-flat-atmospheric"
    assert "林溪" not in markdown["sourceMarkdown"]
    assert "姓名" in markdown["sourceMarkdown"]


def test_explicit_sample_creation_keeps_the_sample_content():
    data = apply_creation_preferences(
        default_resume_data_v2(),
        theme_id="muji-default-autumn",
        from_sample=True,
    )

    assert "林溪" in data["metadata"]["markdown"]["sourceMarkdown"]
