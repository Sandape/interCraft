import type { LineHeightPreset, MujiThemeId } from "@/modules/resume/renderer/types";
import { A4_HEIGHT_PX, A4_WIDTH_PX } from "./constants";
import type { PageBreakDecision, PaginatedResumePreview, ResumePreviewPage } from "./types";

interface PaginateMarkdownHtmlInput {
  html: string;
  lineHeight: LineHeightPreset;
  themeId?: MujiThemeId;
  pageContentHeightPx?: number;
}

type FragmentKind = "atomic" | "heading" | "paragraph" | "list" | "table" | "contact";

interface FragmentBase {
  key: string;
  tagName: string;
  html: string;
  text: string;
  height: number;
  kind: FragmentKind;
  reason: PageBreakDecision["reason"];
}

interface TextPayload {
  tagName: string;
  attrs: string;
  words: string[];
  tokens?: TextToken[];
  originalHtml?: string;
}

interface InlineMark {
  tagName: string;
  attrs: string;
}

type TextToken =
  | { type: "word"; text: string; marks: InlineMark[]; leadingSpace: boolean }
  | { type: "break"; marks: InlineMark[] };

interface ListItemPayload {
  attrs: string;
  html: string;
  text: string;
  words?: string[];
  tokens?: TextToken[];
}

interface ListPayload {
  tagName: "ul" | "ol";
  attrs: string;
  items: ListItemPayload[];
  startIndex: number;
}

interface TableRowPayload {
  html: string;
  text: string;
}

interface TablePayload {
  attrs: string;
  prefixHtml: string;
  headerHtml: string;
  rows: TableRowPayload[];
}

interface ContactSidePayload {
  attrs: string;
}

interface ContactRowPayload {
  sideIndex: number;
  html: string;
  text: string;
}

interface ContactPayload {
  containerAttrs: string;
  sides: ContactSidePayload[];
  rows: ContactRowPayload[];
}

type FlowFragment =
  | (FragmentBase & { kind: "atomic" | "heading" })
  | (FragmentBase & { kind: "paragraph"; payload: TextPayload })
  | (FragmentBase & { kind: "list"; payload: ListPayload })
  | (FragmentBase & { kind: "table"; payload: TablePayload })
  | (FragmentBase & { kind: "contact"; payload: ContactPayload });

interface MeasurementContext {
  measureHtml: (html: string) => number;
  pageContentHeightPx: number | null;
  cleanup: () => void;
}

interface PaginationConfig {
  lineHeight: LineHeightPreset;
  pageContentHeightPx: number;
  measurement: MeasurementContext;
}

interface SplitResult {
  head: FlowFragment;
  tail: FlowFragment | null;
  warnings: string[];
}

const PAGE_PADDING_Y = 72;
const DEFAULT_PAGE_CONTENT_HEIGHT = A4_HEIGHT_PX - PAGE_PADDING_Y;
const TEXT_COLUMNS_CHARS = 88;
const CJK_TOKEN_CHUNK_SIZE = 8;
const CJK_CHARACTER_RE = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]/;
const MIN_PARAGRAPH_LINES = 2;
const INLINE_FORMATTING_TAGS = new Set([
  "a",
  "abbr",
  "b",
  "code",
  "del",
  "em",
  "i",
  "ins",
  "kbd",
  "mark",
  "s",
  "small",
  "span",
  "strong",
  "sub",
  "sup",
  "u",
]);

export function paginateMarkdownHtml({
  html,
  lineHeight,
  themeId,
  pageContentHeightPx,
}: PaginateMarkdownHtmlInput): PaginatedResumePreview {
  const measurement = createMeasurementContext(lineHeight, themeId);
  const resolvedPageHeight = Math.max(
    linePx(lineHeight) * 4,
    Math.floor(pageContentHeightPx ?? measurement.pageContentHeightPx ?? DEFAULT_PAGE_CONTENT_HEIGHT),
  );
  const config: PaginationConfig = {
    lineHeight,
    pageContentHeightPx: resolvedPageHeight,
    measurement,
  };

  try {
    const fragments = parseFragments(html, config);
    if (fragments.length === 0) {
      return makePreview([""], lineHeight, [], []);
    }

    const { pages, breaks, overflowWarnings } = flowFragmentsIntoPages(fragments, config);
    return makePreview(pages.map((page) => page.join("")), lineHeight, breaks, overflowWarnings);
  } finally {
    measurement.cleanup();
  }
}

function flowFragmentsIntoPages(
  fragments: FlowFragment[],
  config: PaginationConfig,
): { pages: string[][]; breaks: PageBreakDecision[]; overflowWarnings: string[] } {
  const queue = [...fragments];
  const pages: string[][] = [];
  const breaks: PageBreakDecision[] = [];
  const overflowWarnings: string[] = [];
  let currentPage: string[] = [];
  let currentHeight = 0;
  let iterationCount = 0;
  const maxIterations = Math.max(500, fragments.length * 200);

  const pushBreakAndPage = (
    reason: PageBreakDecision["reason"],
    beforeNodeKey: string | null,
    afterNodeKey: string | null,
    warnings: string[] = [],
  ) => {
    if (currentPage.length === 0) return;
    breaks.push({ beforeNodeKey, afterNodeKey, reason, warnings });
    pages.push(currentPage);
    currentPage = [];
    currentHeight = 0;
  };

  const appendFragment = (fragment: FlowFragment) => {
    currentPage.push(fragment.html);
    currentHeight = measureCurrentPageHeight();
  };

  const measureCurrentPageHeight = (extraHtml = "") => {
    const html = `${currentPage.join("")}${extraHtml}`;
    return html ? config.measurement.measureHtml(html) : 0;
  };

  while (queue.length > 0) {
    iterationCount += 1;
    if (iterationCount > maxIterations) {
      overflowWarnings.push("Pagination stopped after reaching the safety iteration limit.");
      currentPage.push(queue.map((fragment) => fragment.html).join(""));
      currentHeight = config.pageContentHeightPx;
      queue.length = 0;
      break;
    }

    const fragment = queue[0];
    const next = queue[1];

    if (shouldBreakBeforeHeading(fragment, next, currentHeight, currentPage.length, config)) {
      pushBreakAndPage("avoid_orphan_heading", fragment.key, next?.key ?? null);
      continue;
    }

    queue.shift();
    const candidateHeight = measureCurrentPageHeight(fragment.html);

    if (candidateHeight <= config.pageContentHeightPx) {
      appendFragment(fragment);
      continue;
    }

    const availableHeight = config.pageContentHeightPx - currentHeight;

    if (isSplittable(fragment)) {
      const split = splitFragmentToFit(fragment, availableHeight, config);
      if (split) {
        appendFragment(split.head);
        if (split.tail) {
          queue.unshift(split.tail);
        }
        pushBreakAndPage(
          fragment.reason,
          split.tail?.key ?? queue[0]?.key ?? null,
          queue[0]?.key ?? null,
          split.warnings,
        );
        continue;
      }
    }

    if (currentPage.length > 0) {
      queue.unshift(fragment);
      pushBreakAndPage("page_full", fragment.key, next?.key ?? null);
      continue;
    }

    const warning = `Oversized ${fragment.tagName.toLowerCase()} block may need manual review.`;
    overflowWarnings.push(warning);
    appendFragment(fragment);
    if (queue.length > 0) {
      pushBreakAndPage("oversized_block", queue[0]?.key ?? null, null, [
        `Measured block height ${fragment.height}px exceeds page content height.`,
      ]);
    }
  }

  if (currentPage.length > 0) {
    pages.push(currentPage);
  }

  return { pages, breaks, overflowWarnings };
}

function parseFragments(html: string, config: PaginationConfig): FlowFragment[] {
  if (typeof document === "undefined") {
    return fallbackFragments(html, config);
  }

  const template = document.createElement("template");
  template.innerHTML = html;
  const children = flattenRenderBlocks(Array.from(template.content.children));
  if (children.length === 0 && html.trim()) {
    return fallbackFragments(html, config);
  }

  return children.flatMap((element, index) => createFragment(element as HTMLElement, `block-${index}`, config));
}

function flattenRenderBlocks(elements: Element[]): Element[] {
  const flattened: Element[] = [];
  for (const element of elements) {
    if (
      element instanceof HTMLElement &&
      element.classList.contains("block") &&
      element.children.length > 1
    ) {
      flattened.push(...flattenRenderBlocks(Array.from(element.children)));
    } else {
      flattened.push(element);
    }
  }
  return flattened;
}

function fallbackFragments(html: string, config: PaginationConfig): FlowFragment[] {
  return html
    .split(/(?=<h[1-3]\b|<p\b|<ul\b|<ol\b|<table\b|<div\b|<hr\b|<blockquote\b)/i)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part, index) =>
      createAtomicFragment({
        key: `fallback-${index}`,
        tagName: part.match(/^<([a-z0-9]+)/i)?.[1]?.toLowerCase() ?? "div",
        html: part,
        text: stripTags(part),
        kind: /^<h[1-3]\b/i.test(part) ? "heading" : "atomic",
        reason: "page_full",
        config,
      }),
    );
}

function createFragment(element: HTMLElement, fallbackKey: string, config: PaginationConfig): FlowFragment[] {
  const tagName = element.tagName.toLowerCase();
  const key = element.getAttribute("data-block-id") ?? fallbackKey;

  if (isContactContainer(element)) {
    const contact = createContactFragment(element, key, config);
    if (contact) return [contact];
  }

  if (tagName === "table") {
    const table = createTableFragment(element, key, config);
    if (table) return [table];
  }

  if (tagName === "ul" || tagName === "ol") {
    const list = createListFragment(element, key, config);
    if (list) return [list];
  }

  if (tagName === "p" || tagName === "blockquote" || isPlainTextDiv(element)) {
    const paragraph = createParagraphFragment(element, key, config);
    if (paragraph) return [paragraph];
  }

  return [
    createAtomicFragment({
      key,
      tagName,
      html: element.outerHTML,
      text: element.textContent ?? "",
      kind: /^h[1-3]$/i.test(tagName) ? "heading" : "atomic",
      reason: breakReasonForTag(tagName),
      config,
    }),
  ];
}

function createAtomicFragment({
  key,
  tagName,
  html,
  text,
  kind,
  reason,
  config,
}: {
  key: string;
  tagName: string;
  html: string;
  text: string;
  kind: "atomic" | "heading";
  reason: PageBreakDecision["reason"];
  config: PaginationConfig;
}): FlowFragment {
  return {
    key,
    tagName,
    html,
    text,
    height: config.measurement.measureHtml(html),
    kind,
    reason,
  };
}

function createParagraphFragment(
  element: HTMLElement,
  key: string,
  config: PaginationConfig,
): FlowFragment | null {
  const tokens = textTokensFromElement(element);
  const words = wordsFromTextTokens(tokens);
  if (words.length === 0) return null;
  const attrs = attrsToString(element);
  return makeParagraphFragment(
    {
      key,
      tagName: element.tagName.toLowerCase(),
      attrs,
      words,
      tokens,
      originalHtml: element.outerHTML,
    },
    config,
  );
}

function createListFragment(element: HTMLElement, key: string, config: PaginationConfig): FlowFragment | null {
  const tagName = element.tagName.toLowerCase();
  if (tagName !== "ul" && tagName !== "ol") return null;
  const items = Array.from(element.children)
    .filter((child): child is HTMLElement => child instanceof HTMLElement && child.tagName.toLowerCase() === "li")
    .map((item) => {
      const tokens = textTokensFromElement(item);
      return {
        attrs: attrsToString(item),
        html: item.outerHTML,
        text: item.textContent?.replace(/\s+/g, " ").trim() ?? "",
        words: wordsFromTextTokens(tokens),
        tokens,
      };
    });
  if (items.length === 0) return null;
  return makeListFragment(
    {
      key,
      tagName,
      attrs: attrsToString(element),
      items,
      startIndex: 0,
    },
    config,
  );
}

function createTableFragment(element: HTMLElement, key: string, config: PaginationConfig): FlowFragment | null {
  const tableChildren = Array.from(element.children).filter(
    (child): child is HTMLElement => child instanceof HTMLElement,
  );
  const prefixHtml = tableChildren
    .filter((child) => ["caption", "colgroup"].includes(child.tagName.toLowerCase()))
    .map((child) => child.outerHTML)
    .join("");
  const thead = tableChildren.find((child) => child.tagName.toLowerCase() === "thead");
  const bodyRows = tableChildren
    .flatMap((child) => {
      const tagName = child.tagName.toLowerCase();
      if (tagName === "tbody") return Array.from(child.children);
      if (tagName === "tr") return [child];
      return [];
    })
    .filter((child): child is HTMLElement => child instanceof HTMLElement && child.tagName.toLowerCase() === "tr");

  const firstRowLooksLikeHeader = !thead && bodyRows[0]?.querySelector("th");
  const headerHtml = thead?.outerHTML ?? (firstRowLooksLikeHeader ? `<thead>${bodyRows[0].outerHTML}</thead>` : "");
  const rows = (firstRowLooksLikeHeader ? bodyRows.slice(1) : bodyRows).map((row) => ({
    html: row.outerHTML,
    text: row.textContent?.replace(/\s+/g, " ").trim() ?? "",
  }));

  if (rows.length === 0) return null;
  return makeTableFragment(
    {
      key,
      attrs: attrsToString(element),
      prefixHtml,
      headerHtml,
      rows,
    },
    config,
  );
}

function createContactFragment(element: HTMLElement, key: string, config: PaginationConfig): FlowFragment | null {
  if (!isPureContactContainer(element)) return null;

  const sideElements = Array.from(element.children).filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.classList.contains("resume-contact-side"),
  );
  const sides = sideElements.length > 0 ? sideElements : [element];
  const sidePayloads = sides.map((side, index) => ({
    attrs:
      side === element
        ? ` class="resume-contact-side" data-contact-side="${index === 0 ? "left" : "right"}"`
        : attrsToString(side),
  }));
  const rows = Array.from(element.querySelectorAll(".resume-contact-row"))
    .filter((row): row is HTMLElement => row instanceof HTMLElement)
    .map((row) => {
      const sideIndex = Math.max(
        0,
        sides.findIndex((side) => side === row || side.contains(row)),
      );
      return {
        sideIndex,
        html: row.outerHTML,
        text: row.textContent?.replace(/\s+/g, " ").trim() ?? "",
      };
    });

  if (rows.length === 0) return null;
  return makeContactFragment(
    {
      key,
      containerAttrs: attrsToString(element),
      sides: sidePayloads,
      rows,
    },
    config,
  );
}

function makeParagraphFragment(payload: TextPayload & { key: string }, config: PaginationConfig): FlowFragment {
  const html =
    payload.originalHtml ??
    `<${payload.tagName}${payload.attrs}>${paragraphBodyHtml(payload)}</${payload.tagName}>`;
  return {
    key: payload.key,
    tagName: payload.tagName,
    html,
    text: payload.words.join(" "),
    height: config.measurement.measureHtml(html),
    kind: "paragraph",
    reason: "page_full",
    payload,
  };
}

function makeListFragment(payload: ListPayload & { key: string }, config: PaginationConfig): FlowFragment {
  const attrs = listAttrsForStart(payload);
  const html = `<${payload.tagName}${attrs}>${payload.items.map((item) => item.html).join("")}</${payload.tagName}>`;
  return {
    key: payload.key,
    tagName: payload.tagName,
    html,
    text: payload.items.map((item) => item.text).join(" "),
    height: config.measurement.measureHtml(html),
    kind: "list",
    reason: "keep_list_readable",
    payload,
  };
}

function makeTableFragment(payload: TablePayload & { key: string }, config: PaginationConfig): FlowFragment {
  const html = `<table${payload.attrs}>${payload.prefixHtml}${payload.headerHtml}<tbody>${payload.rows
    .map((row) => row.html)
    .join("")}</tbody></table>`;
  return {
    key: payload.key,
    tagName: "table",
    html,
    text: payload.rows.map((row) => row.text).join(" "),
    height: config.measurement.measureHtml(html),
    kind: "table",
    reason: "keep_table_readable",
    payload,
  };
}

function makeContactFragment(payload: ContactPayload & { key: string }, config: PaginationConfig): FlowFragment {
  const html = `<div${payload.containerAttrs}>${payload.sides
    .map((side, sideIndex) => {
      const rows = payload.rows
        .filter((row) => row.sideIndex === sideIndex)
        .map((row) => row.html)
        .join("");
      return `<div${side.attrs}>${rows}</div>`;
    })
    .join("")}</div>`;
  return {
    key: payload.key,
    tagName: "div",
    html,
    text: payload.rows.map((row) => row.text).join(" "),
    height: config.measurement.measureHtml(html),
    kind: "contact",
    reason: "page_full",
    payload,
  };
}

function isSplittable(fragment: FlowFragment): fragment is Extract<FlowFragment, { kind: "paragraph" | "list" | "table" | "contact" }> {
  return ["paragraph", "list", "table", "contact"].includes(fragment.kind);
}

function splitFragmentToFit(fragment: FlowFragment, availableHeight: number, config: PaginationConfig): SplitResult | null {
  if (!isSplittable(fragment)) return null;
  const targetHeight = Math.min(config.pageContentHeightPx, availableHeight);
  if (targetHeight < minimumFragmentHeight(fragment, config) && availableHeight < config.pageContentHeightPx) {
    return null;
  }

  if (fragment.kind === "paragraph") return splitParagraphFragment(fragment, targetHeight, config);
  if (fragment.kind === "list") return splitListFragment(fragment, targetHeight, config);
  if (fragment.kind === "table") return splitTableFragment(fragment, targetHeight, config);
  return splitContactFragment(fragment, targetHeight, config);
}

function splitParagraphFragment(
  fragment: Extract<FlowFragment, { kind: "paragraph" }>,
  targetHeight: number,
  config: PaginationConfig,
): SplitResult | null {
  const words = fragment.payload.words;
  if (words.length <= 1) return null;

  const cut = findBestWordCut(fragment.payload, words, targetHeight, config);
  if (cut <= 0 || cut >= words.length) return null;

  const head = makeParagraphFragment(
    {
      ...fragment.payload,
      key: `${fragment.key}:part-a`,
      words: words.slice(0, cut),
      tokens: fragment.payload.tokens ? sliceTokensByWordRange(fragment.payload.tokens, 0, cut) : undefined,
      originalHtml: undefined,
    },
    config,
  );
  const tail = makeParagraphFragment(
    {
      ...fragment.payload,
      key: `${fragment.key}:part-b`,
      words: words.slice(cut),
      tokens: fragment.payload.tokens
        ? sliceTokensByWordRange(fragment.payload.tokens, cut, words.length)
        : undefined,
      originalHtml: undefined,
    },
    config,
  );
  return { head, tail, warnings: [] };
}

function splitListFragment(
  fragment: Extract<FlowFragment, { kind: "list" }>,
  targetHeight: number,
  config: PaginationConfig,
): SplitResult | null {
  const items = fragment.payload.items;
  if (items.length === 0) return null;

  const bestCount = findBestItemCount(
    items.length,
    targetHeight,
    (count) =>
      makeListFragment(
        {
          ...fragment.payload,
          key: `${fragment.key}:probe`,
          items: items.slice(0, count),
        },
        config,
      ).height,
  );

  if (bestCount > 0) {
    const headItems = items.slice(0, bestCount);
    const tailItems = items.slice(bestCount);
    let head = makeListFragment(
      { ...fragment.payload, key: `${fragment.key}:items-a`, items: headItems },
      config,
    );
    if (tailItems.length > 0) {
      const remainingHeight = targetHeight - head.height;
      const tailProbe = makeListFragment(
        {
          ...fragment.payload,
          key: `${fragment.key}:items-b-probe`,
          items: tailItems,
          startIndex: fragment.payload.startIndex + bestCount,
        },
        config,
      ) as Extract<FlowFragment, { kind: "list" }>;
      const partial = splitOversizedListItem(tailProbe, remainingHeight, config);
      if (partial?.head.kind === "list" && (!partial.tail || partial.tail.kind === "list")) {
        const combinedHead = makeListFragment(
          {
            ...fragment.payload,
            key: `${fragment.key}:items-a`,
            items: [...headItems, ...partial.head.payload.items],
          },
          config,
        );
        if (combinedHead.height <= targetHeight) {
          return { head: combinedHead, tail: partial.tail, warnings: partial.warnings };
        }
      }
    }
    const tail =
      tailItems.length > 0
        ? makeListFragment(
            {
              ...fragment.payload,
              key: `${fragment.key}:items-b`,
              items: tailItems,
              startIndex: fragment.payload.startIndex + bestCount,
            },
            config,
          )
        : null;
    return { head, tail, warnings: [] };
  }

  return splitOversizedListItem(fragment, targetHeight, config);
}

function splitOversizedListItem(
  fragment: Extract<FlowFragment, { kind: "list" }>,
  targetHeight: number,
  config: PaginationConfig,
): SplitResult | null {
  const [firstItem, ...restItems] = fragment.payload.items;
  const words = firstItem.words && firstItem.words.length > 0 ? firstItem.words : splitWords(firstItem.text);
  if (words.length <= 1) return null;
  const itemPayload: TextPayload = { tagName: "li", attrs: firstItem.attrs, words, tokens: firstItem.tokens };
  const cut = findBestWordCut(itemPayload, words, targetHeight, config);
  if (cut <= 0 || cut >= words.length) return null;
  const headWords = words.slice(0, cut);
  const tailWords = words.slice(cut);
  const headTokens = firstItem.tokens ? sliceTokensByWordRange(firstItem.tokens, 0, cut) : undefined;
  const tailTokens = firstItem.tokens ? sliceTokensByWordRange(firstItem.tokens, cut, words.length) : undefined;

  const headItem = {
    attrs: firstItem.attrs,
    html: `<li${firstItem.attrs}>${paragraphBodyHtml({ words: headWords, tokens: headTokens })}</li>`,
    text: headWords.join(" "),
    words: headWords,
    tokens: headTokens,
  };
  const tailItem = {
    attrs: firstItem.attrs,
    html: `<li${firstItem.attrs}>${paragraphBodyHtml({ words: tailWords, tokens: tailTokens })}</li>`,
    text: tailWords.join(" "),
    words: tailWords,
    tokens: tailTokens,
  };

  const head = makeListFragment(
    { ...fragment.payload, key: `${fragment.key}:li-a`, items: [headItem] },
    config,
  );
  const tail = makeListFragment(
    { ...fragment.payload, key: `${fragment.key}:li-b`, items: [tailItem, ...restItems] },
    config,
  );
  return { head, tail, warnings: [] };
}

function splitTableFragment(
  fragment: Extract<FlowFragment, { kind: "table" }>,
  targetHeight: number,
  config: PaginationConfig,
): SplitResult | null {
  const rows = fragment.payload.rows;
  if (rows.length === 0) return null;
  const bestCount = findBestItemCount(
    rows.length,
    targetHeight,
    (count) =>
      makeTableFragment(
        {
          ...fragment.payload,
          key: `${fragment.key}:probe`,
          rows: rows.slice(0, count),
        },
        config,
      ).height,
  );

  if (bestCount <= 0) {
    if (targetHeight < config.pageContentHeightPx) return null;
    const head = makeTableFragment(
      { ...fragment.payload, key: `${fragment.key}:row-a`, rows: rows.slice(0, 1) },
      config,
    );
    const tailRows = rows.slice(1);
    const tail =
      tailRows.length > 0
        ? makeTableFragment({ ...fragment.payload, key: `${fragment.key}:row-b`, rows: tailRows }, config)
        : null;
    return {
      head,
      tail,
      warnings: [`Table row height ${head.height}px exceeds page content height.`],
    };
  }

  const headRows = rows.slice(0, bestCount);
  const tailRows = rows.slice(bestCount);
  const head = makeTableFragment({ ...fragment.payload, key: `${fragment.key}:rows-a`, rows: headRows }, config);
  const tail =
    tailRows.length > 0
      ? makeTableFragment({ ...fragment.payload, key: `${fragment.key}:rows-b`, rows: tailRows }, config)
      : null;
  return { head, tail, warnings: [] };
}

function splitContactFragment(
  fragment: Extract<FlowFragment, { kind: "contact" }>,
  targetHeight: number,
  config: PaginationConfig,
): SplitResult | null {
  const rows = fragment.payload.rows;
  if (rows.length === 0) return null;
  const bestCount = findBestItemCount(
    rows.length,
    targetHeight,
    (count) =>
      makeContactFragment(
        {
          ...fragment.payload,
          key: `${fragment.key}:probe`,
          rows: rows.slice(0, count),
        },
        config,
      ).height,
  );

  if (bestCount <= 0) {
    if (targetHeight < config.pageContentHeightPx) return null;
    const head = makeContactFragment(
      { ...fragment.payload, key: `${fragment.key}:row-a`, rows: rows.slice(0, 1) },
      config,
    );
    const tailRows = rows.slice(1);
    const tail =
      tailRows.length > 0
        ? makeContactFragment({ ...fragment.payload, key: `${fragment.key}:row-b`, rows: tailRows }, config)
        : null;
    return { head, tail, warnings: [] };
  }

  const headRows = rows.slice(0, bestCount);
  const tailRows = rows.slice(bestCount);
  const head = makeContactFragment({ ...fragment.payload, key: `${fragment.key}:rows-a`, rows: headRows }, config);
  const tail =
    tailRows.length > 0
      ? makeContactFragment({ ...fragment.payload, key: `${fragment.key}:rows-b`, rows: tailRows }, config)
      : null;
  return { head, tail, warnings: [] };
}

function findBestWordCut(
  payload: Pick<TextPayload, "tagName" | "attrs" | "tokens">,
  words: string[],
  targetHeight: number,
  config: PaginationConfig,
): number {
  let low = 1;
  let high = words.length - 1;
  let best = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const html = paragraphProbeHtml(payload, words, mid);
    const height = config.measurement.measureHtml(html);
    if (height <= targetHeight) {
      best = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  while (
    best > 1 &&
    estimatedLineCount(words.slice(best).join(" ")) < MIN_PARAGRAPH_LINES &&
    estimatedLineCount(words.slice(0, best).join(" ")) > MIN_PARAGRAPH_LINES
  ) {
    best -= 1;
  }

  return best;
}

function findBestItemCount(total: number, targetHeight: number, heightForCount: (count: number) => number): number {
  let low = 1;
  let high = total;
  let best = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const height = heightForCount(mid);
    if (height <= targetHeight) {
      best = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return best;
}

function shouldBreakBeforeHeading(
  fragment: FlowFragment,
  next: FlowFragment | undefined,
  currentHeight: number,
  currentPageLength: number,
  config: PaginationConfig,
): boolean {
  if (fragment.kind !== "heading" || !next || currentPageLength === 0) return false;
  const keepHeight = fragment.height + minimumFragmentHeight(next, config);
  return keepHeight <= config.pageContentHeightPx && currentHeight + keepHeight > config.pageContentHeightPx;
}

function minimumFragmentHeight(fragment: FlowFragment, config: PaginationConfig): number {
  if (fragment.kind === "paragraph") {
    return linePx(config.lineHeight) * MIN_PARAGRAPH_LINES + 16;
  }
  if (fragment.kind === "list") {
    return linePx(config.lineHeight) + 16;
  }
  if (fragment.kind === "table") {
    const firstRow = fragment.payload.rows[0];
    if (!firstRow) return linePx(config.lineHeight) + 20;
    return makeTableFragment({ ...fragment.payload, key: `${fragment.key}:min`, rows: [firstRow] }, config).height;
  }
  if (fragment.kind === "contact") {
    const firstRow = fragment.payload.rows[0];
    if (!firstRow) return linePx(config.lineHeight) + 18;
    return makeContactFragment({ ...fragment.payload, key: `${fragment.key}:min`, rows: [firstRow] }, config).height;
  }
  return Math.min(fragment.height, config.pageContentHeightPx);
}

function createMeasurementContext(lineHeight: LineHeightPreset, themeId?: MujiThemeId): MeasurementContext {
  if (typeof document === "undefined" || !document.body) {
    return {
      measureHtml: (html) => estimateHtmlHeight(html, lineHeight),
      pageContentHeightPx: null,
      cleanup: () => undefined,
    };
  }

  const host = document.createElement("article");
  host.className = `markdown-resume-preview height${lineHeight}`;
  if (themeId) host.dataset.theme = themeId;
  host.style.position = "absolute";
  host.style.visibility = "hidden";
  host.style.pointerEvents = "none";
  host.style.left = "-10000px";
  host.style.top = "0";
  host.style.width = `${A4_WIDTH_PX}px`;
  host.style.height = `${A4_HEIGHT_PX}px`;
  host.style.overflow = "hidden";
  host.style.fontSize = "14px";
  host.style.lineHeight = String(lineHeight / 10);

  const content = document.createElement("div");
  content.className = "resume-page-content";
  content.style.boxSizing = "border-box";
  content.style.height = "100%";
  content.style.padding = "36px 46px";

  const probe = document.createElement("div");
  probe.style.display = "flow-root";
  probe.style.width = "100%";

  content.appendChild(probe);
  host.appendChild(content);
  document.body.appendChild(host);

  const computed = window.getComputedStyle(content);
  const paddingTop = Number.parseFloat(computed.paddingTop || "0") || 36;
  const paddingBottom = Number.parseFloat(computed.paddingBottom || "0") || 36;

  return {
    measureHtml: (fragmentHtml) => {
      probe.innerHTML = fragmentHtml;
      const measured =
        Math.ceil(probe.getBoundingClientRect().height) ||
        Math.ceil(probe.scrollHeight) ||
        Array.from(probe.children).reduce((sum, child) => {
          if (!(child instanceof HTMLElement)) return sum;
          return sum + Math.ceil(child.getBoundingClientRect().height);
        }, 0);
      probe.innerHTML = "";
      return measured > 0 ? measured : estimateHtmlHeight(fragmentHtml, lineHeight);
    },
    pageContentHeightPx: A4_HEIGHT_PX - paddingTop - paddingBottom,
    cleanup: () => {
      host.remove();
    },
  };
}

function estimateHtmlHeight(html: string, lineHeight: LineHeightPreset): number {
  if (typeof document !== "undefined") {
    const template = document.createElement("template");
    template.innerHTML = html;
    const elements = Array.from(template.content.children).filter(
      (child): child is HTMLElement => child instanceof HTMLElement,
    );
    if (elements.length > 0) {
      return elements.reduce((sum, element) => sum + estimateElementHeight(element, lineHeight), 0);
    }
  }
  return estimateTextHeight(stripTags(html), lineHeight);
}

function estimateElementHeight(element: HTMLElement, lineHeight: LineHeightPreset): number {
  const tag = element.tagName.toLowerCase();
  if (tag === "h1") return 72;
  if (tag === "h2") return 48;
  if (tag === "h3") return 36;
  if (tag === "table") {
    const rows = Math.max(1, element.querySelectorAll("tr").length);
    return rows * 32 + 20;
  }
  if (tag === "ul" || tag === "ol") {
    const items = Array.from(element.children).filter(
      (child): child is HTMLElement => child instanceof HTMLElement && child.tagName.toLowerCase() === "li",
    );
    if (items.length === 0) return Math.max(24, linePx(lineHeight)) + 12;
    return items.reduce(
      (sum, item) => sum + Math.max(24, estimateTextElementHeight(item, lineHeight)),
      12,
    );
  }
  if (isContactContainer(element)) {
    const rows = Math.max(1, element.querySelectorAll(".resume-contact-row").length);
    return rows * Math.max(22, linePx(lineHeight)) + 18;
  }
  return estimateTextElementHeight(element, lineHeight);
}

function estimateTextElementHeight(element: HTMLElement, lineHeight: LineHeightPreset): number {
  return estimateTextHeight(stripTags(element.innerHTML), lineHeight);
}

function estimateTextHeight(text: string, lineHeight: LineHeightPreset): number {
  return estimatedLineCount(text) * linePx(lineHeight) + 16;
}

function estimatedLineCount(text: string): number {
  const lines = text.trim().split(/\n+/).filter(Boolean);
  if (lines.length === 0) return 1;
  return lines.reduce(
    (sum, line) => sum + Math.max(1, Math.ceil(line.trim().length / TEXT_COLUMNS_CHARS)),
    0,
  );
}

function linePx(lineHeight: LineHeightPreset): number {
  return Math.ceil(14 * (lineHeight / 10));
}

function breakReasonForTag(tagName: string): PageBreakDecision["reason"] {
  if (tagName === "table") return "keep_table_readable";
  if (tagName === "ul" || tagName === "ol") return "keep_list_readable";
  return "page_full";
}

function isContactContainer(element: HTMLElement): boolean {
  return element.classList.contains("resume-contact-container") && isPureContactContainer(element);
}

function isPureContactContainer(element: HTMLElement): boolean {
  if (!element.classList.contains("resume-contact-container")) return false;

  const sideElements = Array.from(element.children).filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.classList.contains("resume-contact-side"),
  );
  const rowCount = element.querySelectorAll(".resume-contact-row").length;
  if (rowCount === 0) return false;

  if (sideElements.length > 0) {
    const containerChildren = effectiveChildNodes(element);
    if (
      containerChildren.some(
        (child) => !(child instanceof HTMLElement) || !child.classList.contains("resume-contact-side"),
      )
    ) {
      return false;
    }
  }

  const rowParents = sideElements.length > 0 ? sideElements : [element];
  return rowParents.every((parent) =>
    effectiveChildNodes(parent).every(
      (child) => child instanceof HTMLElement && child.classList.contains("resume-contact-row"),
    ),
  );
}

function effectiveChildNodes(element: HTMLElement): ChildNode[] {
  return Array.from(element.childNodes).filter((child) => {
    if (child.nodeType !== Node.TEXT_NODE) return true;
    return (child.textContent?.trim().length ?? 0) > 0;
  });
}

function isPlainTextDiv(element: HTMLElement): boolean {
  return (
    element.tagName.toLowerCase() === "div" &&
    element.children.length === 0 &&
    (element.textContent?.trim().length ?? 0) > 0
  );
}

function splitWords(text: string): string[] {
  const tokens: TextToken[] = [];
  appendTextTokens(text, [], tokens, { value: false });
  return wordsFromTextTokens(tokens);
}

function textTokensFromElement(element: HTMLElement): TextToken[] {
  const tokens: TextToken[] = [];
  const pendingSpace = { value: false };
  const visit = (node: ChildNode, marks: InlineMark[]) => {
    if (node.nodeType === Node.TEXT_NODE) {
      appendTextTokens(node.textContent ?? "", marks, tokens, pendingSpace);
      return;
    }

    if (!(node instanceof HTMLElement)) return;
    if (node.tagName.toLowerCase() === "br") {
      tokens.push({ type: "break", marks: [...marks] });
      pendingSpace.value = false;
      return;
    }

    const nextMarks = isPreservedInlineElement(node)
      ? [...marks, { tagName: node.tagName.toLowerCase(), attrs: attrsToString(node) }]
      : marks;
    node.childNodes.forEach((child) => visit(child, nextMarks));
  };

  element.childNodes.forEach((child) => visit(child, []));
  return trimBoundaryBreakTokens(tokens);
}

function appendTextTokens(
  text: string,
  marks: InlineMark[],
  tokens: TextToken[],
  pendingSpace: { value: boolean },
): void {
  const runs = text.matchAll(/\S+/g);
  let cursor = 0;

  for (const match of runs) {
    const run = match[0];
    const index = match.index ?? 0;
    const leadingSpace = pendingSpace.value || /\s/.test(text.slice(cursor, index));
    const chunks = splitTextRunForPagination(run);

    chunks.forEach((chunk, chunkIndex) => {
      tokens.push({
        type: "word",
        text: chunk,
        marks: [...marks],
        leadingSpace: chunkIndex === 0 ? leadingSpace : false,
      });
    });

    pendingSpace.value = false;
    cursor = index + run.length;
  }

  if (/\s/.test(text.slice(cursor))) {
    pendingSpace.value = true;
  }
}

function splitTextRunForPagination(run: string): string[] {
  if (!CJK_CHARACTER_RE.test(run)) return [run];

  const chars = Array.from(run);
  if (chars.length <= CJK_TOKEN_CHUNK_SIZE) return [run];

  const chunks: string[] = [];
  for (let index = 0; index < chars.length; index += CJK_TOKEN_CHUNK_SIZE) {
    chunks.push(chars.slice(index, index + CJK_TOKEN_CHUNK_SIZE).join(""));
  }
  return chunks;
}

function wordsFromTextTokens(tokens: TextToken[]): string[] {
  return tokens.flatMap((token) => (token.type === "word" ? [token.text] : []));
}

function sliceTokensByWordRange(tokens: TextToken[], startWord: number, endWord: number): TextToken[] {
  const sliced: TextToken[] = [];
  let wordIndex = 0;

  for (const token of tokens) {
    if (token.type === "word") {
      if (wordIndex >= startWord && wordIndex < endWord) {
        sliced.push(token);
      }
      wordIndex += 1;
      continue;
    }

    if (wordIndex > startWord && wordIndex < endWord) {
      sliced.push(token);
    }
  }

  return trimBoundaryBreakTokens(sliced);
}

function paragraphBodyHtml(payload: Pick<TextPayload, "words" | "tokens">): string {
  if (payload.tokens) {
    return textTokensToHtml(payload.tokens);
  }
  return escapeHtml(payload.words.join(" "));
}

function paragraphProbeHtml(
  payload: Pick<TextPayload, "tagName" | "attrs" | "tokens">,
  words: string[],
  wordCount: number,
): string {
  const bodyHtml = payload.tokens
    ? textTokensToHtml(sliceTokensByWordRange(payload.tokens, 0, wordCount))
    : escapeHtml(words.slice(0, wordCount).join(" "));
  return `<${payload.tagName}${payload.attrs}>${bodyHtml}</${payload.tagName}>`;
}

function textTokensToHtml(tokens: TextToken[]): string {
  const parts: string[] = [];
  const openMarks: InlineMark[] = [];
  let hasWordInLine = false;

  for (const token of trimBoundaryBreakTokens(tokens)) {
    if (token.type === "break") {
      syncInlineMarks(parts, openMarks, token.marks);
      parts.push("<br>");
      hasWordInLine = false;
      continue;
    }

    if (hasWordInLine) {
      transitionInlineMarks(parts, openMarks, token.marks, token.leadingSpace);
    } else {
      syncInlineMarks(parts, openMarks, token.marks);
    }
    parts.push(escapeHtml(token.text));
    hasWordInLine = true;
  }

  syncInlineMarks(parts, openMarks, []);
  return parts.join("");
}

function syncInlineMarks(parts: string[], openMarks: InlineMark[], nextMarks: InlineMark[]): void {
  const commonPrefixLength = inlineMarkCommonPrefixLength(openMarks, nextMarks);

  for (let index = openMarks.length - 1; index >= commonPrefixLength; index -= 1) {
    parts.push(`</${openMarks[index].tagName}>`);
  }
  openMarks.length = commonPrefixLength;

  for (let index = commonPrefixLength; index < nextMarks.length; index += 1) {
    const mark = nextMarks[index];
    parts.push(`<${mark.tagName}${mark.attrs}>`);
    openMarks.push(mark);
  }
}

function transitionInlineMarks(
  parts: string[],
  openMarks: InlineMark[],
  nextMarks: InlineMark[],
  leadingSpace: boolean,
): void {
  const commonPrefixLength = inlineMarkCommonPrefixLength(openMarks, nextMarks);

  for (let index = openMarks.length - 1; index >= commonPrefixLength; index -= 1) {
    parts.push(`</${openMarks[index].tagName}>`);
  }
  openMarks.length = commonPrefixLength;
  if (leadingSpace) {
    parts.push(" ");
  }

  for (let index = commonPrefixLength; index < nextMarks.length; index += 1) {
    const mark = nextMarks[index];
    parts.push(`<${mark.tagName}${mark.attrs}>`);
    openMarks.push(mark);
  }
}

function inlineMarkCommonPrefixLength(left: InlineMark[], right: InlineMark[]): number {
  let commonPrefixLength = 0;
  while (
    commonPrefixLength < left.length &&
    commonPrefixLength < right.length &&
    sameInlineMark(left[commonPrefixLength], right[commonPrefixLength])
  ) {
    commonPrefixLength += 1;
  }
  return commonPrefixLength;
}

function sameInlineMark(left: InlineMark, right: InlineMark): boolean {
  return left.tagName === right.tagName && left.attrs === right.attrs;
}

function isPreservedInlineElement(element: HTMLElement): boolean {
  return INLINE_FORMATTING_TAGS.has(element.tagName.toLowerCase());
}

function trimBoundaryBreakTokens(tokens: TextToken[]): TextToken[] {
  let start = 0;
  let end = tokens.length;
  while (start < end && tokens[start]?.type === "break") {
    start += 1;
  }
  while (end > start && tokens[end - 1]?.type === "break") {
    end -= 1;
  }
  return tokens.slice(start, end);
}

function attrsToString(element: HTMLElement): string {
  const attrs = Array.from(element.attributes)
    .map((attr) => `${attr.name}="${escapeAttribute(attr.value)}"`)
    .join(" ");
  return attrs ? ` ${attrs}` : "";
}

function listAttrsForStart(payload: ListPayload): string {
  if (payload.tagName !== "ol" || payload.startIndex <= 0 || /\sstart=/.test(payload.attrs)) {
    return payload.attrs;
  }
  return `${payload.attrs} start="${payload.startIndex + 1}"`;
}

function stripTags(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/[ \t\f\v\r]+/g, " ")
    .replace(/ *\n */g, "\n")
    .trim();
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function makePreview(
  pageHtml: string[],
  lineHeight: LineHeightPreset,
  breaks: PageBreakDecision[],
  overflowWarnings: string[],
): PaginatedResumePreview {
  const safePages = pageHtml.length > 0 ? pageHtml : [""];
  const pages: ResumePreviewPage[] = safePages.map((html, pageIndex) => ({
    pageIndex,
    pageNumber: pageIndex + 1,
    html,
    breakBeforeBlockId: breaks[pageIndex - 1]?.beforeNodeKey ?? null,
    breakAfterBlockId: breaks[pageIndex]?.beforeNodeKey ?? null,
  }));

  return {
    pages,
    pageCount: pages.length,
    lineHeight,
    renderVersion: `markdown-pages:${lineHeight}:${pages.length}`,
    overflowWarnings,
    breaks,
  };
}
