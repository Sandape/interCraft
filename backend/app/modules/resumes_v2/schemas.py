"""M032 — Resume v2 Pydantic v2 schemas.

Mirrors the frontend Zod schema in
``src/modules/resume/v2/schema/data.ts``. Drift between the two
is a contract bug per spec contracts/02-resume-data-schema.md §0.

Round-trip guarantees:
- ``ResumeDataV2Pydantic.model_validate(data)`` succeeds on every
  Zod-validated frontend payload.
- ``ResumeDataV2Pydantic.model_dump(mode="json")`` round-trips through
  Pydantic JSON Schema and back.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

# ─────────────────────────────────────────────────────────────────────────────
# Primitives
# ─────────────────────────────────────────────────────────────────────────────

IconName = Annotated[str, StringConstraints(min_length=1, max_length=64)]
# Slug: enforce max length only at the Pydantic layer (422 → too generic).
# Pattern + range validation lives in the service layer so it can return
# 400 INVALID_SLUG per the v2 contract.
SlugStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]
NameStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]
TemplateId = Literal[
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
SectionType = Literal[
    "profiles",
    "experience",
    "education",
    "projects",
    "skills",
    "languages",
    "interests",
    "awards",
    "certifications",
    "publications",
    "volunteer",
    "references",
]
FontWeight = Literal["100", "200", "300", "400", "500", "600", "700", "800", "900"]
LevelType = Literal[
    "hidden",
    "circle",
    "square",
    "rectangle",
    "rectangle-full",
    "progress-bar",
    "icon",
]
PageFormat = Literal["a4", "letter", "free-form"]
MujiThemeId = Literal[
    "muji-default-autumn",
    "muji-minimal-color",
    "muji-flat-atmospheric",
]
SmartOnePageStatus = Literal["idle", "fit", "already-fit", "infeasible"]
RgbaPattern = re.compile(
    r"^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0|1|0?\.\d+)\s*\)$"
)


def RgbaColor() -> type[BaseModel]:
    """Returns a constrained string type enforcing rgba(r,g,b,a) shape."""

    class _Rgba(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: Annotated[
            str,
            StringConstraints(min_length=1, max_length=64, pattern=RgbaPattern.pattern or ""),
        ]

    return _Rgba


# We model RgbaColor as a plain constrained str for the public API.
RgbaColorStr = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=RgbaPattern.pattern or "")
]


# ─────────────────────────────────────────────────────────────────────────────
# ResumeDataV2
# ─────────────────────────────────────────────────────────────────────────────

class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PictureConfig(_Base):
    hidden: bool
    url: str = Field(default="", max_length=2048)
    size: int = Field(ge=32, le=512)
    rotation: int = Field(ge=0, le=360)
    aspectRatio: float = Field(ge=0.5, le=2.5)
    borderRadius: int = Field(ge=0, le=100)
    borderColor: RgbaColorStr
    borderWidth: int = Field(ge=0)
    shadowColor: RgbaColorStr
    shadowWidth: int = Field(ge=0)


class Website(_Base):
    url: str = Field(default="", max_length=2048)
    label: str = Field(default="", max_length=128)


class ItemWebsite(_Base):
    url: str = Field(default="", max_length=2048)
    label: str = Field(default="", max_length=128)
    inlineLink: bool = False


class CustomField(_Base):
    id: str
    icon: IconName
    text: str
    link: str = ""


class Basics(_Base):
    name: str = Field(default="", max_length=128)
    headline: str = Field(default="", max_length=256)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=64)
    location: str = Field(default="", max_length=256)
    website: Website = Field(default_factory=Website)
    customFields: list[CustomField] = Field(default_factory=list, max_length=16)


class Summary(_Base):
    title: str = Field(default="", max_length=128)
    icon: IconName
    columns: int = Field(ge=1, le=6)
    hidden: bool
    content: str = Field(default="", max_length=50000)


class _ItemBase(_Base):
    id: str
    hidden: bool


class ProfileItem(_ItemBase):
    icon: IconName
    iconColor: RgbaColorStr
    network: str
    username: str
    website: ItemWebsite


class RoleItem(_Base):
    id: str
    position: str
    period: str
    description: str


class ExperienceItem(_ItemBase):
    company: str
    position: str
    location: str
    period: str
    website: ItemWebsite
    description: str
    roles: list[RoleItem] = Field(default_factory=list)


class EducationItem(_ItemBase):
    school: str
    degree: str
    area: str
    grade: str
    location: str
    period: str
    website: ItemWebsite
    description: str


class ProjectItem(_ItemBase):
    name: str
    period: str
    website: ItemWebsite
    description: str


class SkillItem(_ItemBase):
    icon: IconName
    iconColor: RgbaColorStr
    name: str
    proficiency: str
    level: int = Field(ge=0, le=5)
    keywords: list[str] = Field(default_factory=list)


class LanguageItem(_ItemBase):
    language: str
    fluency: str
    level: int = Field(ge=0, le=5)


class InterestItem(_ItemBase):
    icon: IconName
    iconColor: RgbaColorStr
    name: str
    keywords: list[str] = Field(default_factory=list)


class AwardItem(_ItemBase):
    title: str
    awarder: str
    date: str
    website: ItemWebsite
    description: str


class CertificationItem(_ItemBase):
    title: str
    issuer: str
    date: str
    website: ItemWebsite
    description: str


class PublicationItem(_ItemBase):
    title: str
    publisher: str
    date: str
    website: ItemWebsite
    description: str


class VolunteerItem(_ItemBase):
    organization: str
    location: str
    period: str
    website: ItemWebsite
    description: str


class ReferenceItem(_ItemBase):
    name: str
    position: str
    website: ItemWebsite
    phone: str
    description: str


class _SectionBase(_Base):
    title: str = Field(default="", max_length=128)
    icon: IconName
    columns: int = Field(ge=1, le=6)
    hidden: bool


class ProfilesSection(_SectionBase):
    items: list[ProfileItem] = Field(default_factory=list, max_length=100)


class ExperienceSection(_SectionBase):
    items: list[ExperienceItem] = Field(default_factory=list, max_length=100)


class EducationSection(_SectionBase):
    items: list[EducationItem] = Field(default_factory=list, max_length=100)


class ProjectsSection(_SectionBase):
    items: list[ProjectItem] = Field(default_factory=list, max_length=100)


class SkillsSection(_SectionBase):
    items: list[SkillItem] = Field(default_factory=list, max_length=100)


class LanguagesSection(_SectionBase):
    items: list[LanguageItem] = Field(default_factory=list, max_length=100)


class InterestsSection(_SectionBase):
    items: list[InterestItem] = Field(default_factory=list, max_length=100)


class AwardsSection(_SectionBase):
    items: list[AwardItem] = Field(default_factory=list, max_length=100)


class CertificationsSection(_SectionBase):
    items: list[CertificationItem] = Field(default_factory=list, max_length=100)


class PublicationsSection(_SectionBase):
    items: list[PublicationItem] = Field(default_factory=list, max_length=100)


class VolunteerSection(_SectionBase):
    items: list[VolunteerItem] = Field(default_factory=list, max_length=100)


class ReferencesSection(_SectionBase):
    items: list[ReferenceItem] = Field(default_factory=list, max_length=100)


class Sections(_Base):
    profiles: ProfilesSection
    experience: ExperienceSection
    education: EducationSection
    projects: ProjectsSection
    skills: SkillsSection
    languages: LanguagesSection
    interests: InterestsSection
    awards: AwardsSection
    certifications: CertificationsSection
    publications: PublicationsSection
    volunteer: VolunteerSection
    references: ReferencesSection


class CustomSection(_SectionBase):
    id: str
    type: SectionType
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


# ─────────────────────────────────────────────────────────────────────────────
# Style rules + metadata
# ─────────────────────────────────────────────────────────────────────────────

class TypographyItem(_Base):
    fontFamily: str = Field(max_length=64)
    fontWeights: list[FontWeight] = Field(min_length=1, max_length=9)
    fontSize: int = Field(ge=6, le=24)
    lineHeight: float = Field(ge=0.5, le=4)


class Typography(_Base):
    body: TypographyItem
    heading: TypographyItem


class PageLayout(_Base):
    fullWidth: bool
    main: list[str] = Field(max_length=32)
    sidebar: list[str] = Field(max_length=32)


class Layout(_Base):
    sidebarWidth: int = Field(ge=10, le=50)
    pages: list[PageLayout] = Field(min_length=1, max_length=10)


class Page(_Base):
    gapX: float = Field(ge=0, le=200)
    gapY: float = Field(ge=0, le=200)
    marginX: float = Field(ge=0, le=200)
    marginY: float = Field(ge=0, le=200)
    format: PageFormat
    locale: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    hideLinkUnderline: bool
    hideIcons: bool
    hideSectionIcons: bool


class LevelDesign(_Base):
    icon: IconName
    type: LevelType


class ColorDesign(_Base):
    primary: RgbaColorStr
    text: RgbaColorStr
    background: RgbaColorStr


class Design(_Base):
    level: LevelDesign
    colors: ColorDesign


class StyleIntent(_Base):
    """Free-form CSS-like intent. All fields optional; nothing else accepted."""

    model_config = ConfigDict(extra="forbid")

    color: RgbaColorStr | None = None
    backgroundColor: RgbaColorStr | None = None
    borderColor: RgbaColorStr | None = None
    textDecorationColor: RgbaColorStr | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    fontSize: int | None = Field(default=None, ge=6, le=48)
    fontWeight: FontWeight | None = None
    fontStyle: Literal["normal", "italic"] | None = None
    lineHeight: float | None = Field(default=None, ge=0.5, le=4)
    letterSpacing: float | None = Field(default=None, ge=-16, le=16)
    textDecoration: Literal["none", "underline", "line-through"] | None = None
    textDecorationStyle: Literal["solid", "dashed", "dotted"] | None = None
    textAlign: Literal["left", "center", "right", "justify"] | None = None
    textTransform: Literal["none", "uppercase", "lowercase", "capitalize"] | None = None
    padding: float | list[float] | None = None
    paddingTop: int | None = Field(default=None, ge=-72, le=72)
    paddingRight: int | None = Field(default=None, ge=-72, le=72)
    paddingBottom: int | None = Field(default=None, ge=-72, le=72)
    paddingLeft: int | None = Field(default=None, ge=-72, le=72)
    marginTop: int | None = Field(default=None, ge=-72, le=72)
    marginRight: int | None = Field(default=None, ge=-72, le=72)
    marginBottom: int | None = Field(default=None, ge=-72, le=72)
    marginLeft: int | None = Field(default=None, ge=-72, le=72)
    rowGap: int | None = Field(default=None, ge=-72, le=72)
    columnGap: int | None = Field(default=None, ge=-72, le=72)
    borderStyle: Literal["solid", "dashed", "dotted"] | None = None
    borderWidth: int | None = Field(default=None, ge=0)
    borderRadius: int | None = Field(default=None, ge=0)


class StyleRuleSlots(_Base):
    section: StyleIntent | None = None
    heading: StyleIntent | None = None
    item: StyleIntent | None = None
    text: StyleIntent | None = None
    secondaryText: StyleIntent | None = None
    link: StyleIntent | None = None
    icon: StyleIntent | None = None
    level: StyleIntent | None = None
    richParagraph: StyleIntent | None = None
    richList: StyleIntent | None = None
    richListItemRow: StyleIntent | None = None
    richListItemContent: StyleIntent | None = None
    richLink: StyleIntent | None = None
    richBold: StyleIntent | None = None
    richMark: StyleIntent | None = None


class _GlobalTarget(_Base):
    scope: Literal["global"]


class _SectionTypeTarget(_Base):
    scope: Literal["sectionType"]
    sectionType: SectionType


class _SectionIdTarget(_Base):
    scope: Literal["sectionId"]
    sectionId: str = Field(min_length=1)


class StyleRule(_Base):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=128)
    enabled: bool
    target: _GlobalTarget | _SectionTypeTarget | _SectionIdTarget
    slots: StyleRuleSlots


class MarkdownSettings(_Base):
    sourceMarkdown: str = Field(default="", max_length=50000)
    themeId: MujiThemeId = "muji-default-autumn"
    manualLineHeight: int = Field(default=19, ge=12, le=25)
    smartOnePageEnabled: bool = False
    smartLineHeight: int | None = Field(default=None, ge=12, le=25)
    previousManualLineHeight: int | None = Field(default=None, ge=12, le=25)
    smartStatus: SmartOnePageStatus = "idle"
    paginationState: Literal["idle", "measuring", "paginated", "warning", "failed"] = "idle"
    pageCount: int = Field(default=1, ge=1)
    legacyConversionStatus: Literal[
        "not_needed", "pending", "converted", "warning", "failed"
    ] = "not_needed"
    legacyConversionWarnings: list[str] = Field(default_factory=list)


class Metadata(_Base):
    template: TemplateId
    layout: Layout
    page: Page
    design: Design
    typography: Typography
    notes: str = Field(default="", max_length=50000)
    styleRules: list[StyleRule] = Field(default_factory=list, max_length=50)
    markdown: MarkdownSettings = Field(default_factory=MarkdownSettings)


class _ResumeDataV2Base(BaseModel):
    """Loose-extra base for the v2 data blob.

    REQ-034: the frontend ships unknown extra keys in partial PUT
    payloads (e.g. ``data.metadata`` with an extra unknown template
    marker). ``extra=ignore`` tolerates these without 422-ing the
    request, while the strict ``_Base`` still rejects typos for the
    inbound/outbound API request models.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ResumeDataV2Pydantic(_ResumeDataV2Base):
    """The complete v2 resume document — round-trips with the frontend Zod schema."""

    picture: PictureConfig
    basics: Basics
    summary: Summary
    sections: Sections
    customSections: list[CustomSection] = Field(default_factory=list)
    metadata: Metadata


# ─────────────────────────────────────────────────────────────────────────────
# API request / response models
# ─────────────────────────────────────────────────────────────────────────────

class ResumeV2CreateIn(_Base):
    name: NameStr
    slug: SlugStr
    template: TemplateId = "pikachu"
    theme_id: MujiThemeId = "muji-default-autumn"
    from_sample: bool = False


class ResumeV2UpdateIn(_Base):
    """PUT body — partial document update.

    REQ-039: ``data`` is a free-form ``dict`` (not the strict
    ``ResumeDataV2Pydantic``) so a frontend PUT that only touches
    one sub-tree (e.g. just ``metadata.template``) doesn't 422 on
    the required sub-fields. The service layer (``merge_resume_data``)
    stitches the partial into the stored full doc, validates the
    template id with a graceful fallback, and only then persists.
    """

    name: NameStr | None = None
    tags: list[str] | None = None
    data: dict[str, Any] | None = None


class ResumeV2Out(_Base):
    id: UUID
    user_id: UUID
    name: str
    slug: str
    tags: list[str]
    is_public: bool
    is_locked: bool
    password_set: bool
    data: dict[str, Any]
    version: int
    # REQ-055 derive fields (optional for backward-compatible clients)
    resume_kind: str = "standard"
    root_resume_id: UUID | None = None
    job_id: UUID | None = None
    root_version_at_derive: int | None = None
    target_page_count: int | None = None
    actual_page_count: int | None = None
    derive_meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ResumeV2ListItemOut(_Base):
    id: UUID
    name: str
    slug: str
    tags: list[str]
    is_public: bool
    is_locked: bool
    version: int
    # REQ-055 — required for resume-center root/derived filtering
    resume_kind: str = "standard"
    job_id: UUID | None = None
    target_page_count: int | None = None
    actual_page_count: int | None = None
    created_at: datetime
    updated_at: datetime
    statistics: dict[str, int | None] | None = None


class ResumeV2ListOut(_Base):
    data: list[ResumeV2ListItemOut]


class ResumeV2DuplicateOut(_Base):
    id: UUID
    name: str
    slug: str
    version: int
    data: dict[str, Any]
    is_public: bool
    is_locked: bool
    password_set: bool


class SharingIn(_Base):
    is_public: bool
    password: str | None = Field(default=None, min_length=6, max_length=64)


class SharingOut(_Base):
    is_public: bool
    password_set: bool
    public_url: str | None = None


class LockIn(_Base):
    locked: bool


class LockOut(_Base):
    is_locked: bool


class StatisticsOut(_Base):
    views: int
    downloads: int
    last_viewed_at: datetime | None = None
    last_downloaded_at: datetime | None = None


class AnalysisOut(_Base):
    status: Literal["success", "failed"]
    analysis: dict[str, Any] | None = None
    failure_reason: str | None = None
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Export (US10 — REQ-036)
# ─────────────────────────────────────────────────────────────────────────────

# Mirrors the 027 export gateway's accepted formats. Per
# specs/032-resume-renderer-v2/contracts/01-rest-api.md §6 the v2
# endpoint additionally accepts "json" so clients can round-trip the
# full ResumeDataV2 without rendering.
ExportFormat = Literal["pdf", "png", "jpeg", "json"]


class ExportRenderIn(_Base):
    """POST body for ``/api/v1/v2/export/render``.

    The pipeline accepts pre-rendered HTML (same shape as
    ``/api/v1/export/render``) plus an optional ``resume_id`` so we
    can attribute the download + bump the counter. When ``format`` is
    ``"json"`` the ``html`` field is ignored and the resume's full
    ``ResumeDataV2`` document is returned verbatim.

    NOTE: ``html`` length validation is intentionally NOT a
    Pydantic-constraint here. We want the handler to return the
    flat ``413 CONTENT_TOO_LARGE`` envelope (per the v2 contract)
    rather than a 422 from Pydantic's ``max_length`` check. The
    handler does the size check before delegating to the gateway.
    """

    html: str = ""
    format: ExportFormat = "pdf"
    resume_id: UUID | None = None
    source_markdown: str | None = None
    theme_id: str | None = None
    line_height: int | None = Field(default=None, ge=12, le=25)
    smart_one_page_enabled: bool | None = None
    pagination_state: str | None = None
    preview_page_count: int | None = Field(default=None, ge=1)
    # REQ-055 — when set, server counts PDF pages and rejects mismatch
    expected_page_count: int | None = Field(default=None, ge=1, le=3)


__all__ = [
    "ResumeDataV2Pydantic",
    "ResumeV2CreateIn",
    "ResumeV2UpdateIn",
    "ResumeV2Out",
    "ResumeV2ListOut",
    "ResumeV2ListItemOut",
    "ResumeV2DuplicateOut",
    "SharingIn",
    "SharingOut",
    "LockIn",
    "LockOut",
    "StatisticsOut",
    "AnalysisOut",
    "ExportFormat",
    "ExportRenderIn",
    "TemplateId",
    "SectionType",
]
