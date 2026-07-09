# Contract: `::: left/right` Contact Container Rendering

## Purpose

Guarantee Muji-compatible contact blocks render as professional aligned resume header/contact regions across the three REQ-047 themes and PDF export.

## Supported Markdown Inputs

```markdown
::: left
icon:phone 13800000000
icon:email linxi@example.com
icon:location Shanghai
:::

::: right
[icon:github GitHub](https://github.com/example)
[icon:link Portfolio](https://example.com/very/long/path)
:::
```

Rows may contain:

- Plain text.
- `icon:*` followed by text.
- Markdown links whose label starts with `icon:*`.
- Unknown icon names.
- Long email, URL, or unbroken identifiers.

## Rendered DOM Contract

The renderer must emit enough structure for consistent alignment:

- A parent left/right contact container.
- One side wrapper per `left` or `right` block.
- One row group per contact row.
- One fixed-width icon slot per row when an icon is present or has a fallback.
- One text/link slot per row.
- Wrapped text starts under the text/link slot, not under the icon slot.

Unknown icons must not remove the icon slot. The fallback may be visually neutral, but row spacing and text alignment must stay stable.

## Theme Contract

Each of the three theme ids must keep:

- Consistent icon size within that theme.
- Consistent icon-to-text baseline alignment.
- Sufficient contrast between icon/text and page background.
- Right-column text alignment that does not detach icons from labels.
- Contact rows readable when text wraps.

## PDF Contract

PDF export must render the same contact row structure or a visually equivalent structure. Exported rows must match live preview alignment within the acceptance tolerance.

## Test Contract

Automated coverage must include:

- Renderer unit tests for plain icon rows, icon-prefixed links, unknown icons, mixed plain rows, and long wrapping rows.
- Theme/component tests for all three theme ids.
- Playwright screenshots for all three themes.
- PDF export verification for at least one contact format lab fixture.

## Acceptance Gates

- Icon-to-text vertical alignment differs by no more than 3 screenshot pixels per row in preview and PDF evidence.
- Wrapped text aligns with the text column.
- Unknown icons do not break row alignment.
- Switching themes does not mutate Markdown source.

