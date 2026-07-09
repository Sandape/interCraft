# REQ-032 v2 — 叶子级验收矩阵

> **目的**：把 `tests/e2e/032-resume-renderer-v2/leaf-acceptance.spec.ts` 中每一条 Playwright 用例，与它所覆盖的"用户可见叶子控件"以及对应的"右侧渲染断言"绑定起来。任何一条用例红 = 对应控件或链路坏掉。

## 验收原则

1. **叶子级**：每个用户可见控件（slider / checkbox / input / select / button）都有 ≥1 条断言 **渲染变化** 的用例。
2. **四类断言**：
   - **CSS var** — 读取 `:root` 上的 `--color-primary` / `--font-body` / `--rs-page-padding-x` 等
   - **inline / computed style** — 读取具体元素的 `borderRadius` / `aspectRatio` / `textAlign` 等
   - **data-attr** — 读取 `data-format` / `data-template-id` / `data-level-icon` 等
   - **innerText / DOM count** — 读取文本包含、列表子项数
3. **fresh resume per test** — 每个 `test.beforeEach` 都调用 `registerAndCreateV2Resume()` 注册新用户 + 新建一份 v2 简历，避免顺序依赖。
4. **data-driven 循环** — 同类 leaf（22 个 swatch、10 个 template、12 个 section × 3 controls、6 个 font-weight）由 `for` 循环生成，避免手写冗余。
5. **Onyx-only trap**：Onyx 模板的 `ROOT_STYLE` 用硬编码 `padding: "32px 40px"`，**不消费** `--rs-page-padding-x/y` CSS var。因此 `page-marginX/Y` 测试读 `:root` CSS var，不读 Onyx padding。

## 验收命令

```bash
# 全文件（本地 ~5-8 min，CI 期望全绿）
npm run e2e -- tests/e2e/032-resume-renderer-v2/leaf-acceptance.spec.ts --project=chromium

# 子集（按 panel 跑）
npm run e2e -- leaf-acceptance.spec.ts -g "C2. Layout"
npm run e2e -- leaf-acceptance.spec.ts -g "F\. RichTextEditor"
npm run e2e -- leaf-acceptance.spec.ts -g "G\. Color picker"

# 后端 down 时 test.skip(true, ...) 优雅跳过
```

## 总览

| Phase | Group | 子集 | 测试数（含循环展开） |
|---|---|---|---|
| 0 | smoke | 1 placeholder | 1 |
| A | Builder Shell & Header | 8 用例 | 8 |
| B | Left SectionsPanel | 3 loop × 12 section | 36 |
| C1-C12 | Right Accordions | 12 accordion + 11 loop | ~50 |
| D1-D15 | Per-Dialog Inputs | 15 dialog × ~5-10 leaf | ~70 |
| F | RichTextEditor Toolbar | 21 button + 4 link sub-control | 25 |
| G | Color picker sweep | 3 slots × 22 swatches | 66 |
| H | Template gallery sweep | 10 templates | 10 |
| **总计** | | | **~266+ tests** |

---

## PHASE A — Builder Shell & Header

| # | Leaf / 操作 | 渲染断言 | Spec test title |
|---|---|---|---|
| A1 | 头部 `resume-name` / `breadcrumb` 渲染 | `[data-testid="editor-header"]` 可见 | `A1. editor-header renders with resume-name + breadcrumb` |
| A2 | `toggle-left-sidebar` 按钮 | `[data-side="left"]` `display === 'none'` | `A2. toggle-left-sidebar hides left-panel (display:none on data-side)` |
| A3 | `toggle-right-sidebar` 按钮 | `[data-side="right"]` `display === 'none'` | `A3. toggle-right-sidebar hides right-panel` |
| A4 | 左侧 resize handle 拖动 | `localStorage.v2.panel-sizes[0]` 数值变大 | `A4. resize-handle-left drag → localStorage v2.panel-sizes[0] grows + persists` |
| A5 | `template-gallery-button` | TemplateGallery modal 出现 | `A5. template-gallery-button opens TemplateGallery modal` |
| A6 | `header-duplicate` 按钮 | URL 跳到新 resume id | `A6. header-duplicate → navigates to new resume URL` |
| A7 | `export-pdf-button` | download 事件触发（env-dependent） | `A7. export-pdf-button triggers PDF download` |
| A8 | preview toolbar 4 按钮 (zoom-in / out / reset / stacking-toggle) | preview scale 属性变化 | `A8. preview toolbar: zoom-in / zoom-out / zoom-reset / stacking-toggle` |

---

## PHASE B — Left Panel SectionsPanel (12 sections × 3 controls = 36)

> 12 section id: `profiles / experience / education / projects / skills / languages / interests / awards / certifications / publications / volunteer / references`。
> 6 个 section (`interests / awards / certifications / publications / volunteer / references`) 被 Onyx 模板的 `sections[id].hidden` 控制整体显隐；其余 6 个仅 per-item `hidden`。

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| B1.{id} × 12 | `section-title-{id}` text input | Onyx 对应 block `<h2>` 文本变更为 `"我的{id}标题"` | `B1.${id}.title input → preview heading shows custom title` |
| B2.{id} × 12 | `section-hidden-{id}` checkbox | (a) ONYX_HONORS_HIDDEN 中：对应 `onyx-{id}` DOM 节点数 === 0；(b) 其余：badge `section-hidden-badge-{id}` 可见 | `B2.${id}.hidden toggle → section visibility reflects on preview` |
| B3.{id} × 12 | `{sectionId}-add-item` 按钮 | 对应 `onyx-{id}` 块的直接子 `<div>` 数 +1 | `B3.${id}.add-item → preview item count grows by 1` |

---

## PHASE C — Right Panel Accordions (C1-C12)

### C1. Template accordion (2 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C1.1 | 当前模板名称 | 可见文本 | `C1.1 current template name is shown` |
| C1.2 | `settings-template-open` 按钮 | TemplateGallery modal 出现 | `C1.2 settings-template-open button opens TemplateGallery` |

### C2. Layout accordion (5 + 5 loop = 10 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C2.1 | `layout-sidebar-width` 默认值 35 | value span 文本 === "35" | `C2.1 sidebar-width slider default 35 → value span shows 35` |
| C2.2.{v=10,25,35,45,50} | `layout-sidebar-width` slider 设值 | value span 文本同步 | `C2.2 sidebar-width slider value=${v} → value span mirrors ${v}` |
| C2.3 | `layout-add-page` | 新增 `[data-page-index="1"]` card | `C2.3 add-page → new page card appears at index 1` |
| C2.4 | `layout-fullwidth-{i}` switch | `aria-pressed` 切换 | `C2.4 fullwidth switch → aria-pressed toggles` |
| C2.5 | `layout-delete-page-{i}` 唯一 page | disabled | `C2.5 delete-page disabled when only 1 page` |
| C2.6 | add then delete | 回到 1 page | `C2.6 add then delete → back to 1 page` |
| C2.7 | main drop zone | 可见 | `C2.7 main drop zone visible per page` |

### C3. Typography accordion (2 scopes × ~10 leaf = 18 tests)

> 每个 scope (`body` / `heading`) 独立一组叶子。

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C3.1.body / heading | 字体下拉 + weight 按钮渲染 | 6 fonts + 6 weight buttons | `C3.1.${scope} panel renders with 6 fonts + 6 weight buttons` |
| C3.2.{family × 6 × 2} | `typography-{scope}-family` select | `--font-${scope}` CSS var === `${family}` | `C3.2.${scope} family select → --font-${scope} CSS var updates to "${family}"` |
| C3.3.{size × 4 × 2} | `typography-{scope}-fontSize` (6-24) | `--font-size-${scope}` CSS var === `${size}pt` | `C3.3.${scope} fontSize ${size} → --font-size-${scope} CSS var = "${size}pt"` |
| C3.4.{lh × 4 × 2} | `typography-{scope}-lineHeight` (0.5-4.0) | `--line-height-${scope}` CSS var === `${lh}` | `C3.4.${scope} lineHeight ${lh} → --line-height-${scope} CSS var = "${lh}"` |
| C3.5.{w × 6 × 2} | `typography-{scope}-weight-{w}` button | `aria-pressed === 'true'` | `C3.5.${scope} weight ${w} button → aria-pressed=true` |

### C4. Design accordion (4 + 22×3 + 7 + 4 = ~50 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C4.1.{slot × 3} | `color-picker-{slot}` 22 个 swatch 渲染 | `.color-swatch` 数 === 22 | `C4.1.${slot} color-picker exposes 22 swatches` |
| C4.2.{slot × 3} | `color-input-{slot}` text 改色 | `--color-${slot}` CSS var 匹配 | `C4.2.${slot} color-input text → --color-${slot} CSS var matches` |
| C4.3.{slot × 3} | `color-native-{slot}` 原生 picker | `--color-${slot}` 转 hex | `C4.3.${slot} color-native input → --color-${slot} CSS var matches hex` |
| C4.4.{level × 7} | `level-type-select` | `--level-icon` CSS var / `data-level-icon` 反映 | `C4.4 level-type select "${lv}" → --level-icon CSS var / data-level-icon reflects` |
| C4.5 | `level-icon-picker` search | 过滤 options | `C4.5 level-icon-picker search filters options` |
| C4.6.{icon × 4} | `level-icon-option-{icon}` 按钮 | `data-level-icon="${icon}"` 在 preview 出现 | `C4.6 level-icon-option-${icon} → data-level-icon="${icon}" on preview` |

### C5. Styles accordion (7 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C5.1 | `styles-panel` 渲染 | rule-count + add-rule button 可见 | `C5.1 styles-panel renders with rule-count + add-rule button` |
| C5.2 | add-rule 按钮 | 列表数 +1 | `C5.2 add-rule → rule list grows by 1` |
| C5.3 | toggle rule | `aria-pressed` 切换 | `C5.3 toggle a rule → aria-pressed changes` |
| C5.4 | delete rule | 列表数 -1 | `C5.4 delete a rule → list shrinks` |
| C5.5 | 3 scope radios | dialog 内 3 radios 可见 | `C5.5 3 scope radios present in dialog` |
| C5.6 | 4 tabs | dialog 内 4 tabs 可见 | `C5.6 4 tabs present in dialog` |
| C5.7 | edit rule | dialog 打开 + 显示已有 label | `C5.7 edit a rule → dialog opens with existing label` |

### C6. Page accordion (3 + 4×4 loop = 13 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C6.1.{fmt × 3} | `page-format-{fmt}` radio | `preview-pane[data-format="${fmt}"]` | `C6.1 page-format "${fmt}" radio → preview data-format="${fmt}"` |
| C6.2 | `page-format` (其他预设) | 同上 | `C6.2 page-format ...` |
| C6.3.{v × 4} | `page-marginX` (0-200) | `--rs-page-padding-x` CSS var === `${v}pt` | `C6.3 page-marginX ${v} → --rs-page-padding-x CSS var = "${v}pt"` |
| C6.4.{v × 4} | `page-marginY` | `--rs-page-padding-y` CSS var === `${v}pt` | `C6.4 page-marginY ${v} → --rs-page-padding-y CSS var = "${v}pt"` |
| C6.5.{v × 3} | `page-gapX` | `--rs-gap-x` CSS var === `${v}pt` | `C6.5 page-gapX ${v} → --rs-gap-x CSS var = "${v}pt"` |
| C6.6.{v × 3} | `page-gapY` | `--rs-gap-y` CSS var === `${v}pt` | `C6.6 page-gapY ${v} → --rs-gap-y CSS var = "${v}pt"` |
| C6.7 | `page-locale` text | preview 不报错（locale 校验通过） | `C6.7 page-locale text ...` |
| C6.8 | `page-hideLinkUnderline` toggle | preview 内 `<a>` `textDecoration === 'none'` | `C6.8 page-hideLinkUnderline toggle → preview <a> text-decoration = none` |
| C6.9 | `page-hideIcons` toggle | `--rs-hide-icons` CSS var === '1' | `C6.9 page-hideIcons toggle → --rs-hide-icons CSS var = ...` |
| C6.10 | `page-hideSectionIcons` toggle | `--rs-hide-section-icons` CSS var === '1' | `C6.10 page-hideSectionIcons toggle → --rs-hide-section-icons CSS var = ...` |

### C7. Notes accordion (2 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C7.1 | `notes-panel` 渲染 | `rich-text-editor` 可见 | `C7.1 notes-panel renders with rich-text-editor` |
| C7.2 | 编辑器输入 | `.tiptap` 内文本变更 | `C7.2 typing text updates editor content` |

### C8. Sharing accordion (4 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C8.1 | sharing-panel 渲染 | public-toggle + URL input 可见 | `C8.1 sharing-panel renders with public-toggle + URL input` |
| C8.2 | public toggle ON | URL input enabled | `C8.2 public toggle ON → URL input is enabled` |
| C8.3 | set-password + remove-password 按钮 | 可见 | `C8.3 set-password button + remove-password button present` |
| C8.4 | copy-url 按钮 | 可见 | `C8.4 copy-url button present` |

### C9. Statistics accordion (2 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C9.1 | statistics-panel 渲染 | 可见 | `C9.1 statistics-panel renders` |
| C9.2 | views / downloads 计数 | 数值或空状态 | `C9.2 shows views / downloads counters or empty state` |

### C10. Analysis accordion (2 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C10.1 | analysis-panel 渲染 | 可见 | `C10.1 analysis-panel renders` |
| C10.2 | analyze-button 点击 | 可点（LLM 模式下可能 long） | `C10.2 analyze-button clickable (may take long if LLM is on)` |

### C11. Export accordion (2 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C11.1 | export-panel 渲染 | JSON + PDF 按钮可见 | `C11.1 export-panel renders with JSON + PDF buttons` |
| C11.2 | JSON download | download 事件触发 | `C11.2 JSON download triggers` |

### C12. Information accordion (1 test)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| C12.1 | information-panel | version + id 可见 | `C12.1 information-panel shows version + id` |

---

## PHASE D — Per-Dialog Inputs (D1-D15)

### D1. BasicsDialog (8 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D1.0 | dialog 打开 | `basics-cancel` 可见 | `D1.0 dialog opens and has cancel` |
| D1.{name/headline/email/phone/location/website-label} | text input | preview 反映 `${value}` | `D1.${field} input → preview reflects "${value}"` |
| D1.website-url | text input | preview contact row 显示 URL | `D1.website-url input → preview contact row shows URL` |
| D1.custom-field add | button | custom-field row 数 +1 | `D1.custom-field add → custom-field row count grows` |
| D1.custom-field text | input | preview contact 显示自定义文本 | `D1.custom-field text → preview contact shows custom text` |

### D2. PictureDialog (4 + 9 loop + 1 = ~20 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D2.0 | dialog 打开 | 可见 | `D2.0 dialog opens` |
| D2.hidden | checkbox | `onyx-picture` DOM count === 0 | `D2.hidden checkbox → onyx-picture disappears from preview` |
| D2.size × {32,64,96,128,256} | number (32-512) | `<img>` width === `${v}px` | `D2.size ${v} → onyx-picture <img> width = ${v}px` |
| D2.rotation × {0,45,90,180,270,360} | number (0-360) | `transform.includes("rotate(${v}deg)")` | `D2.rotation ${v}° → img transform contains rotate(${v}deg)` |
| D2.aspectRatio × {0.5,1.0,1.5,2.0,2.5} | number (0.5-2.5) | `aspectRatio` 匹配 `${v}` 或 `auto` | `D2.aspectRatio ${v} → img aspect-ratio = ${v}` |
| D2.borderRadius × {0,25,50,100} | number (0-100) | `borderRadius === '${v}px'` | `D2.borderRadius ${v} → img border-radius = ${v}px` |
| D2.borderWidth × {0,1,5,20} | number (0-40) | `borderWidth === '${v}px'` | `D2.borderWidth ${v} → img border-width = ${v}px` |
| D2.borderColor | text input | `borderColor === 'rgb(255, 0, 0)'` | `D2.borderColor red → img border-color rgb(255,0,0)` |
| D2.shadowWidth × {0,5,20,40} | number (0-40) | `boxShadow` 非空（v>0 时） | `D2.shadowWidth ${v} → img box-shadow non-empty when v>0` |

### D3. ProfileDialog (8 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D3.0 | dialog 打开 | 可见 | `D3.0 dialog opens via profiles add-item` |
| D3.network | text input | `onyx-profiles` 包含网络名 | `D3.network input → onyx-profiles contains network name` |
| D3.website-url + label | text | preview 包含 label | `D3.website-url + label → preview contains label` |
| D3.inlineLink | checkbox | `aria-checked` 切换 | `D3.inlineLink checkbox toggles aria-checked` |
| D3.hidden | checkbox | `onyx-profiles` 不可见（无可见 item） | `D3.hidden checkbox → onyx-profiles disappears when no items visible` |
| D3.icon-name | text input | row 的 `data-icon-name` 反映 | `D3.icon-name input → data-icon-name on row reflects` |
| D3.icon-color | color picker | 接受 hex | `D3.icon-color picker accepts hex` |
| D3.icon-picker-trigger | button | popover 打开 | `D3.icon-picker-trigger opens popover` |

### D4. ExperienceDialog (9 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D4.0 | dialog 打开 | 可见 | `D4.0 dialog opens via experience add-item` |
| D4.{company,position,location,period} | text input | `onyx-experience` 包含 `${value}` | `D4.${field} input → onyx-experience contains "${value}"` |
| D4.description | textarea | `onyx-experience` 包含描述文本 | `D4.description textarea → onyx-experience contains description text` |
| D4.website-url + label | text | 渲染 link | `D4.website-url + label → onyx-experience renders link` |
| D4.add-role | button | roles list +1 | `D4.add-role → roles list grows` |
| D4.role-position | text input | 包含 role text | `D4.role-position input → onyx-experience contains role text` |
| D4.hidden | checkbox | item 过滤 | `D4.hidden checkbox → item filtered out of onyx-experience` |

### D5. EducationDialog (10 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D5.0 | dialog 打开 | 可见 | `D5.0 dialog opens via education add-item` |
| D5.{school,degree,area,grade,location,period} | text input | `onyx-education` 包含 `${value}` | `D5.${field} input → onyx-education contains "${value}"` |
| D5.description | textarea | 渲染 description | `D5.description textarea → onyx-education renders description` |
| D5.add-course | button | courses list +1 | `D5.add-course → courses list grows` |
| D5.course | text input | 显示 course 文本 | `D5.course input → onyx-education shows course text` |
| D5.website | inlineLink toggle | aria-checked 切换 | `D5.website inlineLink toggle` |
| D5.hidden | checkbox | item 过滤 | `D5.hidden checkbox → item filtered` |

### D6. ProjectsDialog (7 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D6.0 | dialog 打开 | 可见 | `D6.0 dialog opens via projects add-item` |
| D6.{name,period} | text input | `onyx-projects` 包含 `${value}` | `D6.${field} input → onyx-projects contains "${value}"` |
| D6.description | textarea | 渲染 description | `D6.description textarea → onyx-projects renders description` |
| D6.add-highlight | button | highlights list +1 | `D6.add-highlight → highlights list grows` |
| D6.highlight | text input | 渲染 highlight 文本 | `D6.highlight input → onyx-projects renders highlight text` |
| D6.website url + label | text | 渲染 | `D6.website url + label render` |
| D6.hidden | checkbox | item 过滤 | `D6.hidden checkbox → item filtered` |

### D7. SkillsDialog (10 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D7.0 | dialog 打开 | 可见 | `D7.0 dialog opens via skills add-item` |
| D7.name | text input | `onyx-skills` 包含 skill name | `D7.name input → onyx-skills contains skill name` |
| D7.proficiency | text input | `onyx-skills` 显示 proficiency | `D7.proficiency input → onyx-skills shows proficiency` |
| D7.level × {0,2,4,5} | slider | `onyx-skills` 渲染对应 level | `D7.level slider ${v} → onyx-skills renders ${v} level` |
| D7.level × {0,3,5} | input | 与 slider 同步 | `D7.level input ${v} syncs with slider` |
| D7.icon | text input | 接受 Lucide name | `D7.icon input accepts Lucide name` |
| D7.icon-color | text input | 接受 hex | `D7.icon-color accepts hex` |
| D7.add-keyword | button | keywords list +1 | `D7.add-keyword → keywords list grows` |
| D7.keyword | text input | 显示 keyword | `D7.keyword input → onyx-skills shows keyword` |
| D7.hidden | checkbox | item 过滤 | `D7.hidden checkbox → item filtered` |

### D8. LanguageDialog (6 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D8.0 | dialog 打开 | 可见 | `D8.0 dialog opens via languages add-item` |
| D8.language | text input | `onyx-languages` 包含 language | `D8.language input → onyx-languages contains language` |
| D8.fluency | text input | 包含 fluency | `D8.fluency input → onyx-languages contains fluency` |
| D8.level × {0,3,5} | slider | `skills-level-label` 反映 | `D8.level slider ${v} → skills-level-label reflects` |
| D8.level × {1,4} | input | 与 slider 同步 | `D8.level input syncs with slider` |
| D8.hidden | checkbox | item 过滤 | `D8.hidden checkbox → item filtered` |

### D9. InterestsDialog (7 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D9.0 | dialog 打开 | 可见 | `D9.0 dialog opens via interests add-item` |
| D9.name | text input | `onyx-interests` 包含 interest name | `D9.name input → onyx-interests contains interest name` |
| D9.icon | text input | 接受 Lucide name | `D9.icon input accepts Lucide name` |
| D9.icon-color | text input | 接受 hex | `D9.icon-color accepts hex` |
| D9.add-keyword | button | list +1 | `D9.add-keyword → list grows` |
| D9.keyword | text input | 显示 keyword | `D9.keyword input → onyx-interests shows keyword` |
| D9.hidden | checkbox | section 整体消失（Onyx honors section.hidden） | `D9.hidden checkbox → section disappears (Onyx honors section.hidden)` |

### D10. AwardsDialog (6 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D10.0 | dialog 打开 | 可见 | `D10.0 dialog opens via awards add-item` |
| D10.{title,awarder,date} | text input | `onyx-awards` 包含 `${value}` | `D10.${field} input → onyx-awards contains "${value}"` |
| D10.website url + label | text | 渲染 | `D10.website url + label` |
| D10.description | rich text | 渲染 | `D10.description rich text → onyx-awards renders` |
| D10.hidden | checkbox | item 过滤 | `D10.hidden checkbox → item filtered` |
| D10.cancel | button | dialog 关闭 | `D10.cancel closes dialog` |

### D11. CertificationsDialog (5 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D11.0 | dialog 打开 | 可见 | `D11.0 dialog opens via certifications add-item` |
| D11.{title,issuer,date} | text input | `onyx-certifications` 包含 `${value}` | `D11.${field} input → onyx-certifications contains "${value}"` |
| D11.website url + label | text | 渲染 | `D11.website url + label` |
| D11.description | rich text | 渲染 | `D11.description rich text` |
| D11.hidden | checkbox | item 过滤 | `D11.hidden checkbox → item filtered` |

### D12. PublicationsDialog (5 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D12.0 | dialog 打开 | 可见 | `D12.0 dialog opens via publications add-item` |
| D12.{title,publisher,date} | text input | `onyx-publications` 包含 `${value}` | `D12.${field} input → onyx-publications contains "${value}"` |
| D12.website url + label | text | 渲染 | `D12.website url + label` |
| D12.description | rich text | 渲染 | `D12.description rich text` |
| D12.hidden | checkbox | item 过滤 | `D12.hidden checkbox → item filtered` |

### D13. VolunteerDialog (5 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D13.0 | dialog 打开 | 可见 | `D13.0 dialog opens via volunteer add-item` |
| D13.{organization,location,period} | text input | `onyx-volunteer` 包含 `${value}` | `D13.${field} input → onyx-volunteer contains "${value}"` |
| D13.website url + label | text | 渲染 | `D13.website url + label` |
| D13.description | rich text | 渲染 | `D13.description rich text` |
| D13.hidden | checkbox | item 过滤 | `D13.hidden checkbox → item filtered` |

### D14. ReferencesDialog (5 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D14.0 | dialog 打开 | 可见 | `D14.0 dialog opens via references add-item` |
| D14.{name,position,phone} | text input | `onyx-references` 包含 `${value}` | `D14.${field} input → onyx-references contains "${value}"` |
| D14.website url + label | text | 渲染 | `D14.website url + label` |
| D14.description | rich text | 渲染 | `D14.description rich text` |
| D14.hidden | checkbox | item 过滤 | `D14.hidden checkbox → item filtered` |

### D15. CustomSectionDialog (8 tests)

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| D15.0 | dialog 打开 | 可见 | `D15.0 dialog opens via custom add-item` |
| D15.title | text input | preview 包含 custom title | `D15.title input → preview contains custom title` |
| D15.columns × {1,2,3} | slider | `custom-columns-input` 匹配 | `D15.columns slider ${v} → custom-columns-input matches ${v}` |
| D15.icon | text input | 接受 Lucide name | `D15.icon input accepts Lucide name` |
| D15.type × 12 | select | 接受每个 SectionType | `D15.type select accepts each of 12 SectionType options` |
| D15.hidden | checkbox | aria-checked 切换 | `D15.hidden checkbox toggles` |
| D15.add-item | button | custom-items-list +1 | `D15.add-item → custom-items-list grows` |
| D15.items cap 100 | button | cap-error 可见（env-dependent） | `D15.items cap at 100 → custom-items-cap-error visible` |

---

## PHASE F — RichTextEditor Toolbar (25 tests)

> 所有 F 测试在 AwardsDialog 的 `description` 字段打开 RichTextEditor 后运行（type "test" + Ctrl+A）。

| # | Leaf (`data-testid`) | 渲染断言 | Spec test title |
|---|---|---|---|
| F.bold | `rtb-bold` | 编辑器 HTML 包含 `<strong>` | `F.bold → editor HTML contains <strong>` |
| F.italic | `rtb-italic` | 包含 `<em>` | `F.italic → editor HTML contains <em>` |
| F.strike | `rtb-strike` | 包含 `<s>` | `F.strike → editor HTML contains <s>` |
| F.highlight | `rtb-highlight` | 包含 `<mark>` | `F.highlight → editor HTML contains <mark>` |
| F.heading-1 | `rtb-heading-1` | 包含 `<h1>` | `F.heading-1 → editor HTML contains <h1>` |
| F.heading-2 | `rtb-heading-2` | 包含 `<h2>` | `F.heading-2 → editor HTML contains <h2>` |
| F.heading-3 | `rtb-heading-3` | 包含 `<h3>` | `F.heading-3 → editor HTML contains <h3>` |
| F.align-left | `rtb-align-left` | 目标 `p/h1/h2/h3` `textAlign ∈ {left, start}` | `F.align-left → editor element textAlign is "left"` |
| F.align-center | `rtb-align-center` | `textAlign === 'center'` | `F.align-center → editor element textAlign is "center"` |
| F.align-right | `rtb-align-right` | `textAlign === 'right'` | `F.align-right → editor element textAlign is "right"` |
| F.align-justify | `rtb-align-justify` | `textAlign === 'justify'` | `F.align-justify → editor element textAlign is "justify"` |
| F.bullet-list | `rtb-bullet-list` | 包含 `<ul>` | `F.bullet-list → editor HTML contains <ul>` |
| F.ordered-list | `rtb-ordered-list` | 包含 `<ol>` | `F.ordered-list → editor HTML contains <ol>` |
| F.indent | `rtb-indent`（先 bullet-list） | `li` `paddingLeft` 变大 | `F.indent inside list → list item gets padding-left > 0` |
| F.outdent | `rtb-outdent`（先 indent） | `li` `paddingLeft` 变小 | `F.outdent inside indented list → list item padding-left decreases` |
| F.inline-code | `rtb-inline-code` | 包含 `<code>` 且不含 `<pre>` | `F.inline-code → editor HTML contains <code> (not <pre>)` |
| F.code-block | `rtb-code-block` | 包含 `<pre><code>` | `F.code-block → editor HTML contains <pre><code>` |
| F.hard-break | `rtb-hard-break` | 包含 `<br>` | `F.hard-break → editor HTML contains <br>` |
| F.hr | `rtb-hr` | 包含 `<hr>` | `F.hr → editor HTML contains <hr>` |
| F.link button | `rtb-link`（带选区） | `rtb-link-prompt` 可见 + input 可见 | `F.link button opens prompt when text selected` |
| F.link-input + apply | `rtb-link-input` + `rtb-link-apply` | 包含 `<a href="https://example.com/test">` | `F.link-input + apply → editor HTML contains <a href="https://…">` |
| F.link-apply rejects | `rtb-link-apply` (javascript:) | `rich-text-editor-error` 可见 | `F.link-apply rejects non-http(s) URL → rich-text-editor error visible` |
| F.link-cancel | `rtb-link-cancel` | prompt 关闭 | `F.link-cancel closes the prompt` |
| F.link-remove | `rtb-link-remove` | （在 prompt 内，移除 link mark） | （覆盖在 F.link-input + apply 后续） |
| F.fullscreen | `rtb-fullscreen` | Modal 标题 `Rich Text Editor (Fullscreen)` 可见 | `F.fullscreen → opens modal with rich-text-editor` |

---

## PHASE G — Color Picker Sweep (3 slots × 22 swatches = 66 tests)

> 全部由 `for` 循环生成。每条点击 `swatch-${i}` 后读 `--color-${slot}` CSS var 与预设 `SWATCH_RGBA[i]` 对比。

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| G.{slot ∈ primary/text/background}.swatch-{i=0..21} | `color-picker-${slot} .color-swatch:nth(${i})` | `--color-${slot}` CSS var === `SWATCH_RGBA[i]` | `G.${slot}.swatch-${i} → --color-${slot} CSS var applied` |

22 个 swatch rgba 预设（与 Onyx 默认色板对齐）：

| idx | rgba |
|---|---|
| 0 | `rgba(0, 0, 0, 1)` |
| 1 | `rgba(33, 37, 41, 1)` |
| 2 | `rgba(73, 80, 87, 1)` |
| 3 | `rgba(134, 142, 150, 1)` |
| 4 | `rgba(173, 181, 189, 1)` |
| 5 | `rgba(206, 212, 218, 1)` |
| 6 | `rgba(248, 249, 250, 1)` |
| 7 | `rgba(255, 255, 255, 1)` |
| 8 | `rgba(255, 0, 0, 1)` |
| 9 | `rgba(253, 126, 20, 1)` |
| 10 | `rgba(255, 193, 7, 1)` |
| 11 | `rgba(40, 167, 69, 1)` |
| 12 | `rgba(13, 202, 240, 1)` |
| 13 | `rgba(13, 110, 253, 1)` |
| 14 | `rgba(102, 16, 242, 1)` |
| 15 | `rgba(214, 51, 132, 1)` |
| 16 | `rgba(121, 85, 72, 1)` |
| 17 | `rgba(33, 37, 41, 0.75)` |
| 18 | `rgba(33, 37, 41, 0.5)` |
| 19 | `rgba(33, 37, 41, 0.25)` |
| 20 | `rgba(0, 0, 0, 0)` |
| 21 | `rgba(0, 0, 0, 0)` |

---

## PHASE H — Template Gallery Sweep (10 tests)

> 全部由 `for (const tpl of TEMPLATE_IDS)` 循环生成。
> 注意：Onyx 之外的 9 个模板（azurill / kakuna / chikorita / ditgar / bronzor / pikachu / lapras / scizor / rhyhorn）在 `templates/index.ts` 的 dispatcher 中 **fall back** 到 Onyx —— 因此 `data-template-id` 属性反映选择，但实际渲染永远是 Onyx。本断言只检验 **dispatcher 选择被记录**，而非模板布局差异。

| # | Leaf | 渲染断言 | Spec test title |
|---|---|---|---|
| H.{tpl ∈ onyx/azurill/kakuna/chikorita/ditgar/bronzor/pikachu/lapras/scizor/rhyhorn} | TemplateGallery 中 `template-card` 按钮 | `preview-pane[data-template-id="${tpl}"]` | `H.${tpl}. switch to "${tpl}" → preview-pane data-template-id reflects selection` |

---

## 已知陷阱（与 lessons-learned 同步）

| 陷阱 | 触发条件 | 处理 |
|---|---|---|
| 受控 input 不响应 `fill()` | React 受控 number / text input | `setInputValue()` 用 native setter 模式（lessons-learned 2026-06-26） |
| 500ms debounce + 网络 roundtrip | leaf 操作后立即断言可能漏 | `waitForSave()` 等 version+1，最多重试 3 次 backoff |
| Tiptap 编辑器卸载丢选区 | 关闭 dialog 后重开 | 每个 F 测试重新 type + Ctrl+A（lessons-learned 2026-06-26） |
| Onyx ROOT_STYLE 硬编码 padding | `page-marginX/Y` 改 CSS var 不影响 Onyx 视觉 | 断言读 `:root` CSS var，不读 Onyx padding |
| Onyx 仅 6 section 响应 `section.hidden` | 切 experience/skills hidden 整体不消失 | 用 `ONYX_HONORS_HIDDEN` 集合分支断言 |
| Tiptap 不消费部分 toolbar | indent / outdent 顶层 paragraph 是 no-op | 在 bullet-list 上下文里操作 |
| Slider aria-valuenow 异步 | 设值后立即读 | 设值后 `waitForTimeout(100)` |
| 9 个非 Onyx 模板 fall back | data-template-id 改变但渲染不变 | H 测试只断言 dispatcher 选择被记录 |
| dnd-kit drag 不响应 `dragTo()` | B3 add-item 后续拖拽 | 当前用 button click 模拟 add，drag 单独覆盖 |
| Backend down / 启动慢 | 整文件 0 pass | `test.beforeAll` 调 `isBackendUp()`，失败则 `test.skip(true, ...)` |

## 关联文档

- 测试规范：`tests/e2e/032-resume-renderer-v2/leaf-acceptance.spec.ts` (2594 行, ~266+ tests)
- 实施计划：`C:\Users\30803\.claude\plans\keen-spinning-wigderson.md`
- v2 spec：`specs/032-resume-renderer-v2/`
- Onyx 模板：`src/modules/resume/v2/templates/onyx/Template.tsx`
- PreviewPane：`src/modules/resume/v2/editor/center/PreviewPane.tsx`
- 教训记录：`lessons-learned.md` (2026-06-26 native setter / Tiptap selection)
- Cycle 4 ship-ready false negative：`memory/cycle4_ship_ready_false_negative.md`