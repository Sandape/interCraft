# Resume Editor v3 for InterCraft v2

Status: active / planned  
Created: 2026-07-06

This is the first active InterCraft v2 product-development spec after the v1 seal. Existing REQ directories before `047` are historical/baseline material unless this spec explicitly reopens a requirement.

## Current Scope

1. Markdown resume rendering
2. Three resume rendering themes
3. Line spacing adjustment
4. Smart one-page
5. PDF and Markdown export

## Primary Artifacts

- Feature spec: `spec.md`
- Implementation plan: `plan.md`
- Research decisions: `research.md`
- Data model: `data-model.md`
- Contracts: `contracts/`
- Validation guide: `quickstart.md`
- Implementation tasks: `tasks.md`
- Requirement status: `requirements-status.md`
- Requirements checklist: `checklists/requirements.md`
- Competitor research evidence: `../../docs/evidence/v3-editor-research/muji-2026-07-06/RESEARCH.md`

## Clarified Decisions

The clarification session on 2026-07-06 resolved the first-version decisions:

- Fully replicate Muji's scoped functionality and rendering effects.
- First version themes: 默认（秋风同款）, 极简色, 平面大气主题.
- Markdown dialect includes Muji-compatible `::: left/right`, `icon:*`, icon-prefixed links, literal task-list rendering, strikethrough, and external URL images.
- Line spacing presets are integers 12 through 25.
- Smart one-page temporarily overrides manual line spacing and restores it when disabled.
- Local image upload/crop is out of scope for this first version.
