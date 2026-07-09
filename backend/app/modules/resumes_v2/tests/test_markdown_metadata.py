from app.modules.resumes_v2.defaults import default_resume_data_v2
from app.modules.resumes_v2.schemas import ResumeDataV2Pydantic


def test_default_resume_data_contains_markdown_metadata():
    data = default_resume_data_v2()

    markdown = data["metadata"]["markdown"]
    assert markdown["themeId"] == "muji-default-autumn"
    assert markdown["manualLineHeight"] == 19
    assert markdown["smartOnePageEnabled"] is False
    assert markdown["smartLineHeight"] is None

    parsed = ResumeDataV2Pydantic.model_validate(data)
    assert parsed.metadata.markdown.themeId == "muji-default-autumn"


def test_markdown_metadata_accepts_scoped_themes_and_line_heights():
    for theme_id in [
        "muji-default-autumn",
        "muji-minimal-color",
        "muji-flat-atmospheric",
    ]:
        data = default_resume_data_v2()
        data["metadata"]["markdown"]["themeId"] = theme_id
        data["metadata"]["markdown"]["manualLineHeight"] = 12
        parsed = ResumeDataV2Pydantic.model_validate(data)
        assert parsed.metadata.markdown.themeId == theme_id
        assert parsed.metadata.markdown.manualLineHeight == 12
