# Research: Resume Editor v3 for InterCraft v2

## Decision: Fully replicate scoped Muji behavior

**Rationale**: Product clarification explicitly requires全面复刻木及的功能和效果 within the narrowed first-version scope. The competitor evidence already covers three target themes, Markdown syntax rendering, line-height menu, smart one-page behavior, and export entry points.

**Alternatives considered**:

- Approximate Muji themes with InterCraft-native design: rejected because the user wants replication, not inspiration.
- Standard Markdown only: rejected because Muji-specific containers/icons are core to the observed resume effect.

## Decision: Use existing `src/modules/resume` boundaries

**Rationale**: The repo already has self-contained resume renderer, themes, pagination, converter, editor, and v2 API areas. Reusing these boundaries satisfies Library-First and avoids reintroducing broad v1/v2 scope.

**Alternatives considered**:

- Create a new `resume-v3` module: rejected because it duplicates existing renderer/theme/pagination boundaries and increases migration risk.
- Modify global editor infrastructure: rejected because the feature is resume-specific.

## Decision: Markdown dialect is Muji-compatible

**Rationale**: The renderer must support standard Markdown plus Muji-compatible `::: left/right`, `icon:*`, icon-prefixed links, inline-code tags, literal task-list syntax, strikethrough, table layout, and external URL images.

**Alternatives considered**:

- InterCraft-only syntax: rejected because it would fail the replication goal.
- GitHub task-list checkbox rendering: rejected because Muji keeps `[x]` and `[ ]` literal.

## Decision: Ship exactly three fixed themes

**Rationale**: Product clarification fixed the first-version theme set to 默认（秋风同款）, 极简色, and 平面大气主题. These map to the competitor evidence and provide concrete visual acceptance targets.

**Alternatives considered**:

- Any three Muji themes later: rejected because it leaves acceptance ambiguous.
- Similar but not exact themes: rejected because it weakens the replication requirement.

## Decision: Line spacing presets are integers 12-25

**Rationale**: Muji exposes numeric line-height presets from 12 through 25. Replicating this range makes UI, state, and tests concrete.

**Alternatives considered**:

- Three presets only: rejected because it loses Muji parity.
- Custom range: rejected because no product reason was given to diverge.

## Decision: Smart one-page temporarily overrides manual line spacing

**Rationale**: Observed Muji behavior changed the preview class from compact `height12` to `height20` when smart one-page was enabled. Product clarification chose temporary override with restoration when disabled.

**Alternatives considered**:

- Permanently rewrite manual spacing: rejected because it loses user intent.
- Suggest-only mode: rejected because it does not replicate Muji behavior.

## Decision: Markdown images support external URLs only

**Rationale**: Muji rendered `![alt](url)` external image syntax. Local upload/crop would expand scope beyond the first version.

**Alternatives considered**:

- Add uploads and cropping: deferred as outside first-version scope.
- Disable images: rejected because Muji renders Markdown images and image rendering is part of Markdown parity.

## Decision: Export contract separates PDF and Markdown

**Rationale**: Muji exposes Markdown export under `文件 > 导出md`; header `导 出` behaves as the PDF direct export entry. InterCraft should present unambiguous PDF and Markdown export actions with progress/failure states.

**Alternatives considered**:

- One combined export menu only: rejected because the user requires PDF or MD and Muji has distinct entry behavior.
- Export without visible progress: rejected because observed lack of visible feedback is a UX risk.

