# ResumeDataV2 JSON Schema

This file is the **machine-readable** version of the data model. The same shape
is enforced at three layers:

1. Frontend Zod parser (TypeScript).
2. Backend Pydantic v2 model (Python).
3. PostgreSQL `jsonb` GIN index (optional, for query helpers).

The schema below is hand-curated and authoritative. Drift between this file
and the implementations is a contract bug.

---

## 1. Root

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://intercraft.local/schemas/resume-data-v2.json",
  "title": "ResumeDataV2",
  "type": "object",
  "additionalProperties": true,           // forward-compatible
  "required": ["picture", "basics", "summary", "sections", "customSections", "metadata"],
  "properties": {
    "picture":       { "$ref": "#/$defs/PictureConfig" },
    "basics":        { "$ref": "#/$defs/Basics" },
    "summary":       { "$ref": "#/$defs/Summary" },
    "sections":      { "$ref": "#/$defs/Sections" },
    "customSections":{ "type": "array", "items": { "$ref": "#/$defs/CustomSection" } },
    "metadata":      { "$ref": "#/$defs/Metadata" }
  }
}
```

---

## 2. $defs

### 2.1 PictureConfig

```json
{
  "type": "object",
  "required": ["hidden","url","size","rotation","aspectRatio","borderRadius","borderColor","borderWidth","shadowColor","shadowWidth"],
  "properties": {
    "hidden":        { "type": "boolean" },
    "url":           { "type": "string", "maxLength": 2048 },
    "size":          { "type": "integer", "minimum": 32, "maximum": 512 },
    "rotation":      { "type": "integer", "minimum": 0, "maximum": 360 },
    "aspectRatio":   { "type": "number",  "minimum": 0.5, "maximum": 2.5 },
    "borderRadius":  { "type": "integer", "minimum": 0, "maximum": 100 },
    "borderColor":   { "$ref": "#/$defs/RgbaColor" },
    "borderWidth":   { "type": "integer", "minimum": 0 },
    "shadowColor":   { "$ref": "#/$defs/RgbaColor" },
    "shadowWidth":   { "type": "integer", "minimum": 0 }
  }
}
```

### 2.2 Basics

```json
{
  "type": "object",
  "required": ["name","headline","email","phone","location","website","customFields"],
  "properties": {
    "name":         { "type": "string", "maxLength": 128 },
    "headline":     { "type": "string", "maxLength": 256 },
    "email":        { "type": "string", "format": "email", "maxLength": 254 },
    "phone":        { "type": "string", "maxLength": 64 },
    "location":     { "type": "string", "maxLength": 256 },
    "website":      { "$ref": "#/$defs/Website" },
    "customFields": {
      "type": "array", "maxItems": 16,
      "items": { "$ref": "#/$defs/CustomField" }
    }
  }
}
```

### 2.3 Summary

```json
{
  "type": "object",
  "required": ["title","icon","columns","hidden","content"],
  "properties": {
    "title":   { "type": "string", "maxLength": 128 },
    "icon":    { "$ref": "#/$defs/IconName" },
    "columns": { "type": "integer", "minimum": 1, "maximum": 6 },
    "hidden":  { "type": "boolean" },
    "content": { "type": "string", "maxLength": 50000 }
  }
}
```

### 2.4 Sections (discriminated by item shape)

```json
{
  "type": "object",
  "required": ["profiles","experience","education","projects","skills","languages","interests","awards","certifications","publications","volunteer","references"],
  "properties": {
    "profiles":      { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/ProfileItem" } },
    "experience":    { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/ExperienceItem" } },
    "education":     { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/EducationItem" } },
    "projects":      { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/ProjectItem" } },
    "skills":        { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/SkillItem" } },
    "languages":     { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/LanguageItem" } },
    "interests":     { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/InterestItem" } },
    "awards":        { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/AwardItem" } },
    "certifications":{ "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/CertificationItem" } },
    "publications":  { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/PublicationItem" } },
    "volunteer":     { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/VolunteerItem" } },
    "references":    { "$ref": "#/$defs/SectionBase", "x-items": { "$ref": "#/$defs/ReferenceItem" } }
  }
}
```

### 2.5 Section base

```json
{
  "type": "object",
  "required": ["title","icon","columns","hidden","items"],
  "properties": {
    "title":   { "type": "string", "maxLength": 128 },
    "icon":    { "$ref": "#/$defs/IconName" },
    "columns": { "type": "integer", "minimum": 1, "maximum": 6 },
    "hidden":  { "type": "boolean" },
    "items":   { "type": "array", "maxItems": 100 }
  }
}
```

### 2.6 Item types (abbreviated)

Each typed item extends `ItemBase` (`{ id: UUID, hidden: boolean }`) with the
fields below. Full definitions live in
`backend/app/modules/resumes_v2/schema.py` and
`frontend/src/modules/resume/v2/schema/items.ts`.

| Type | Fields |
|---|---|
| ProfileItem | network, username, website (ItemWebsite), icon, iconColor |
| ExperienceItem | company, position, location, period, website, description, roles[] |
| EducationItem | school, degree, area, grade, location, period, website, description |
| ProjectItem | name, period, website, description |
| SkillItem | name, proficiency, level (0..5), keywords[], icon, iconColor |
| LanguageItem | language, fluency, level (0..5) |
| InterestItem | name, keywords[], icon, iconColor |
| AwardItem | title, awarder, date, website, description |
| CertificationItem | title, issuer, date, website, description |
| PublicationItem | title, publisher, date, website, description |
| VolunteerItem | organization, location, period, website, description |
| ReferenceItem | name, position, website, phone, description |

### 2.7 Metadata

```json
{
  "type": "object",
  "required": ["template","layout","page","design","typography","notes","styleRules"],
  "properties": {
    "template":   { "$ref": "#/$defs/TemplateId" },
    "layout":     { "$ref": "#/$defs/Layout" },
    "page":       { "$ref": "#/$defs/Page" },
    "design":     { "$ref": "#/$defs/Design" },
    "typography": { "$ref": "#/$defs/Typography" },
    "notes":      { "type": "string", "maxLength": 50000 },
    "styleRules": { "type": "array", "maxItems": 50, "items": { "$ref": "#/$defs/StyleRule" } }
  }
}
```

### 2.8 Layout

```json
{
  "type": "object",
  "required": ["sidebarWidth","pages"],
  "properties": {
    "sidebarWidth": { "type": "integer", "minimum": 10, "maximum": 50 },
    "pages": {
      "type": "array", "minItems": 1, "maxItems": 10,
      "items": { "$ref": "#/$defs/PageLayout" }
    }
  }
}

{ "PageLayout": {
    "type": "object",
    "required": ["fullWidth","main","sidebar"],
    "properties": {
      "fullWidth": { "type": "boolean" },
      "main":      { "type": "array", "items": { "type": "string" }, "maxItems": 32 },
      "sidebar":   { "type": "array", "items": { "type": "string" }, "maxItems": 32 }
    }
} }
```

### 2.9 Page

```json
{
  "type": "object",
  "required": ["gapX","gapY","marginX","marginY","format","locale","hideLinkUnderline","hideIcons","hideSectionIcons"],
  "properties": {
    "gapX":      { "type": "number", "minimum": 0, "maximum": 200 },
    "gapY":      { "type": "number", "minimum": 0, "maximum": 200 },
    "marginX":   { "type": "number", "minimum": 0, "maximum": 200 },
    "marginY":   { "type": "number", "minimum": 0, "maximum": 200 },
    "format":    { "enum": ["a4","letter","free-form"] },
    "locale":    { "type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$" },
    "hideLinkUnderline":  { "type": "boolean" },
    "hideIcons":          { "type": "boolean" },
    "hideSectionIcons":   { "type": "boolean" }
  }
}
```

### 2.10 Design

```json
{
  "type": "object",
  "required": ["colors","level"],
  "properties": {
    "colors": {
      "type": "object",
      "required": ["primary","text","background"],
      "properties": {
        "primary":     { "$ref": "#/$defs/RgbaColor" },
        "text":        { "$ref": "#/$defs/RgbaColor" },
        "background":  { "$ref": "#/$defs/RgbaColor" }
      }
    },
    "level": {
      "type": "object",
      "required": ["icon","type"],
      "properties": {
        "icon": { "$ref": "#/$defs/IconName" },
        "type": { "enum": ["hidden","circle","square","rectangle","rectangle-full","progress-bar","icon"] }
      }
    }
  }
}
```

### 2.11 Typography

```json
{
  "type": "object",
  "required": ["body","heading"],
  "properties": {
    "body":    { "$ref": "#/$defs/TypographyItem" },
    "heading": { "$ref": "#/$defs/TypographyItem" }
  }
}

{ "TypographyItem": {
    "type": "object",
    "required": ["fontFamily","fontWeights","fontSize","lineHeight"],
    "properties": {
      "fontFamily":  { "type": "string", "maxLength": 64 },
      "fontWeights": { "type": "array", "items": { "$ref": "#/$defs/FontWeight" }, "minItems": 1, "maxItems": 9 },
      "fontSize":    { "type": "integer", "minimum": 6, "maximum": 24 },
      "lineHeight":  { "type": "number",  "minimum": 0.5, "maximum": 4 }
    }
} }
```

### 2.12 StyleRule

```json
{
  "type": "object",
  "required": ["id","enabled","target","slots"],
  "properties": {
    "id":      { "type": "string", "minLength": 1, "maxLength": 64 },
    "label":   { "type": "string", "maxLength": 128 },
    "enabled": { "type": "boolean" },
    "target":  {
      "oneOf": [
        { "type": "object", "required": ["scope"], "properties": { "scope": { "const": "global" } } },
        { "type": "object", "required": ["scope","sectionType"],
          "properties": { "scope": { "const": "sectionType" }, "sectionType": { "$ref": "#/$defs/SectionType" } } },
        { "type": "object", "required": ["scope","sectionId"],
          "properties": { "scope": { "const": "sectionId" }, "sectionId": { "type": "string", "minLength": 1 } } }
      ]
    },
    "slots": { "$ref": "#/$defs/StyleRuleSlots" }
  }
}

{ "StyleRuleSlots": {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": false,
    "properties": {
      "section":            { "$ref": "#/$defs/StyleIntent" },
      "heading":            { "$ref": "#/$defs/StyleIntent" },
      "item":               { "$ref": "#/$defs/StyleIntent" },
      "text":               { "$ref": "#/$defs/StyleIntent" },
      "secondaryText":      { "$ref": "#/$defs/StyleIntent" },
      "link":               { "$ref": "#/$defs/StyleIntent" },
      "icon":               { "$ref": "#/$defs/StyleIntent" },
      "level":              { "$ref": "#/$defs/StyleIntent" },
      "richParagraph":      { "$ref": "#/$defs/StyleIntent" },
      "richList":           { "$ref": "#/$defs/StyleIntent" },
      "richListItemRow":    { "$ref": "#/$defs/StyleIntent" },
      "richListItemContent":{ "$ref": "#/$defs/StyleIntent" },
      "richLink":           { "$ref": "#/$defs/StyleIntent" },
      "richBold":           { "$ref": "#/$defs/StyleIntent" },
      "richMark":           { "$ref": "#/$defs/StyleIntent" }
    }
} }

{ "StyleIntent": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "color":               { "$ref": "#/$defs/RgbaColor" },
      "backgroundColor":     { "$ref": "#/$defs/RgbaColor" },
      "borderColor":         { "$ref": "#/$defs/RgbaColor" },
      "textDecorationColor": { "$ref": "#/$defs/RgbaColor" },
      "opacity":             { "type": "number", "minimum": 0, "maximum": 1 },
      "fontSize":            { "type": "integer", "minimum": 6, "maximum": 48 },
      "fontWeight":          { "$ref": "#/$defs/FontWeight" },
      "fontStyle":           { "enum": ["normal","italic"] },
      "lineHeight":          { "type": "number", "minimum": 0.5, "maximum": 4 },
      "letterSpacing":       { "type": "number", "minimum": -16, "maximum": 16 },
      "textDecoration":      { "enum": ["none","underline","line-through"] },
      "textDecorationStyle": { "enum": ["solid","dashed","dotted"] },
      "textAlign":           { "enum": ["left","center","right","justify"] },
      "textTransform":       { "enum": ["none","uppercase","lowercase","capitalize"] },
      "padding":             { "oneOf": [ { "type":"number" }, { "type":"array","items":{"type":"number"} } ] },
      "paddingTop":          { "type": "integer", "minimum": -72, "maximum": 72 },
      "paddingRight":        { "type": "integer", "minimum": -72, "maximum": 72 },
      "paddingBottom":       { "type": "integer", "minimum": -72, "maximum": 72 },
      "paddingLeft":         { "type": "integer", "minimum": -72, "maximum": 72 },
      "marginTop":           { "type": "integer", "minimum": -72, "maximum": 72 },
      "marginRight":         { "type": "integer", "minimum": -72, "maximum": 72 },
      "marginBottom":        { "type": "integer", "minimum": -72, "maximum": 72 },
      "marginLeft":          { "type": "integer", "minimum": -72, "maximum": 72 },
      "rowGap":              { "type": "integer", "minimum": -72, "maximum": 72 },
      "columnGap":           { "type": "integer", "minimum": -72, "maximum": 72 },
      "borderStyle":         { "enum": ["solid","dashed","dotted"] },
      "borderWidth":         { "type": "integer", "minimum": 0 },
      "borderRadius":        { "type": "integer", "minimum": 0 }
    }
} }
```

---

## 3. Enums & primitives

```json
{ "TemplateId": { "enum": ["onyx","azurill","kakuna","chikorita","ditgar","bronzor","pikachu","lapras","scizor","rhyhorn"] } }

{ "SectionType": { "enum": ["profiles","experience","education","projects","skills","languages","interests","awards","certifications","publications","volunteer","references"] } }

{ "FontWeight": { "enum": ["100","200","300","400","500","600","700","800","900"] } }

{ "IconName": { "type": "string", "minLength": 1, "maxLength": 64 } }

{ "RgbaColor": { "type": "string", "pattern": "^rgba\\(\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*\\d{1,3}\\s*,\\s*(0|1|0?\\.\\d+)\\s*\\)$" } }

{ "Website": {
    "type": "object",
    "required": ["url","label"],
    "properties": {
      "url":   { "type": "string", "maxLength": 2048 },
      "label": { "type": "string", "maxLength": 128 }
    }
} }

{ "ItemWebsite": { "allOf": [ { "$ref": "#/$defs/Website" }, {
    "type": "object",
    "required": ["inlineLink"],
    "properties": { "inlineLink": { "type": "boolean" } }
} ] } }
```

---

## 4. Examples

### 4.1 Minimal valid resume

```json
{
  "picture": { "hidden": true, "url": "", "size": 80, "rotation": 0, "aspectRatio": 1, "borderRadius": 0, "borderColor": "rgba(0,0,0,0.5)", "borderWidth": 0, "shadowColor": "rgba(0,0,0,0.5)", "shadowWidth": 0 },
  "basics":  { "name": "", "headline": "", "email": "", "phone": "", "location": "", "website": {"url":"","label":""}, "customFields": [] },
  "summary": { "title": "Summary", "icon": "file-text", "columns": 1, "hidden": false, "content": "" },
  "sections": {
    "profiles":       { "title":"","icon":"link","columns":1,"hidden":false,"items":[] },
    "experience":     { "title":"","icon":"briefcase","columns":1,"hidden":false,"items":[] },
    "education":      { "title":"","icon":"graduation-cap","columns":1,"hidden":false,"items":[] },
    "projects":       { "title":"","icon":"code","columns":1,"hidden":false,"items":[] },
    "skills":         { "title":"","icon":"wrench","columns":1,"hidden":false,"items":[] },
    "languages":      { "title":"","icon":"languages","columns":1,"hidden":false,"items":[] },
    "interests":      { "title":"","icon":"heart","columns":1,"hidden":false,"items":[] },
    "awards":         { "title":"","icon":"trophy","columns":1,"hidden":false,"items":[] },
    "certifications": { "title":"","icon":"award","columns":1,"hidden":false,"items":[] },
    "publications":   { "title":"","icon":"book-open","columns":1,"hidden":false,"items":[] },
    "volunteer":      { "title":"","icon":"hand-heart","columns":1,"hidden":false,"items":[] },
    "references":     { "title":"","icon":"phone","columns":1,"hidden":false,"items":[] }
  },
  "customSections": [],
  "metadata": {
    "template": "pikachu",
    "layout":   { "sidebarWidth": 35, "pages": [{ "fullWidth": false, "main": ["summary","experience","education"], "sidebar": ["skills","languages"] }] },
    "page":     { "gapX":4,"gapY":6,"marginX":14,"marginY":12,"format":"a4","locale":"zh-CN","hideLinkUnderline":false,"hideIcons":false,"hideSectionIcons":true },
    "design":   { "colors": { "primary":"rgba(0,132,209,1)","text":"rgba(0,0,0,1)","background":"rgba(255,255,255,1)" }, "level": { "icon":"star","type":"circle" } },
    "typography": { "body": { "fontFamily":"IBM Plex Sans","fontWeights":["400","500"],"fontSize":10,"lineHeight":1.5 }, "heading": { "fontFamily":"IBM Plex Sans","fontWeights":["600"],"fontSize":14,"lineHeight":1.5 } },
    "notes": "",
    "styleRules": []
  }
}
```

### 4.2 Sample with one Experience item

```json
{
  "id": "0192a3b4-...",
  "hidden": false,
  "company": "Acme Corp",
  "position": "Senior Engineer",
  "location": "Remote",
  "period": "2022 – Present",
  "website": { "url": "https://acme.example", "label": "Acme", "inlineLink": true },
  "description": "<p>Led <strong>5-engineer</strong> team...</p>",
  "roles": [
    { "id": "...", "position": "Tech Lead", "period": "2024 – Present", "description": "<p>...</p>" }
  ]
}
```

---

## 5. Versioning

- The `$id` of this schema includes a content hash: `…v2-1.json`. A breaking
  change bumps the suffix.
- New optional fields are NOT breaking and do not change the `$id`.
- New optional enum members ARE breaking for the **frontend** (must be added
  to the crosswalk). They are non-breaking for **stored data** if existing
  rows remain valid.