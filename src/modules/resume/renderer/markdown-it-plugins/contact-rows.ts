import type MarkdownIt from "markdown-it";

import svgMap from "../icons/svg-map";

const BREAK_RE = /<br\s*\/?>\s*/gi;
const SVG_RE = /<svg\b[\s\S]*?<\/svg>/i;
const LINK_WITH_SVG_RE = /^<a\b(?<attrs>[^>]*)>\s*(?<svg><svg\b[\s\S]*?<\/svg>)\s*(?<label>[\s\S]*?)<\/a>$/i;
const LINK_WITH_ICON_TEXT_RE = /^<a\b(?<attrs>[^>]*)>\s*icon:(?<icon>[a-z0-9_-]+)\s+(?<label>[\s\S]*?)<\/a>$/i;
const PLAIN_ICON_RE = /^icon:(?<icon>[a-z0-9_-]+)\s+(?<label>[\s\S]*)$/i;
const INLINE_ROW_TAGS = new Set(["a", "span", "strong", "em", "b", "i", "code", "small"]);

export default function contactRowsPlugin(_md: MarkdownIt): void {
  // The row normalization runs after Markdown rendering because markdown-it
  // emits contact lines as one paragraph with <br> separators. Keeping this
  // plugin registered documents the dialect extension in the parser assembly.
}

export function normalizeContactRows(html: string): string {
  if (typeof document === "undefined") return html;

  const template = document.createElement("template");
  template.innerHTML = html;

  repairNestedRightSides(template.content);

  for (const container of Array.from(template.content.querySelectorAll(".lr-container"))) {
    if (!(container instanceof HTMLElement)) continue;
    const sides = Array.from(container.children).filter(
      (child): child is HTMLElement =>
        child instanceof HTMLElement && (child.classList.contains("left") || child.classList.contains("right")),
    );
    if (sides.length === 0) continue;

    const parsedSides = sides.map(parseContactSide);
    if (parsedSides.some((side) => side === null)) continue;

    const parsedRows = parsedSides.flatMap((side) => side?.parsedRows ?? []);
    if (!parsedRows.some(isContactLikeRow)) continue;

    container.classList.add("resume-contact-container");
    sides.forEach((side, index) => {
      const parsed = parsedSides[index];
      if (!parsed) return;
      const contactSide = side.classList.contains("right") ? "right" : "left";
      side.classList.add("resume-contact-side");
      side.setAttribute("data-contact-side", contactSide);
      side.innerHTML = parsed.rows.map(renderContactRow).join("");
    });
  }

  return template.innerHTML;
}

function repairNestedRightSides(root: DocumentFragment): void {
  for (const container of Array.from(root.querySelectorAll(".lr-container"))) {
    if (!(container instanceof HTMLElement)) continue;

    const directLeft = Array.from(container.children).find(
      (child): child is HTMLElement => child instanceof HTMLElement && child.classList.contains("left"),
    );
    if (!directLeft) continue;

    const nestedRight = Array.from(directLeft.children).find(
      (child): child is HTMLElement => child instanceof HTMLElement && child.classList.contains("right"),
    );
    if (!nestedRight) continue;

    directLeft.after(nestedRight);
  }

  for (const container of Array.from(root.querySelectorAll(".lr-container"))) {
    if (!(container instanceof HTMLElement)) continue;
    const leakedChildren = Array.from(container.children).filter(
      (child): child is HTMLElement =>
        child instanceof HTMLElement &&
        !child.classList.contains("left") &&
        !child.classList.contains("right"),
    );
    let previous: ChildNode = container;
    for (const leaked of leakedChildren) {
      previous.after(leaked);
      previous = leaked;
    }
  }
}

interface ParsedContactSide {
  rows: string[];
  parsedRows: ParsedRow[];
}

function parseContactSide(side: HTMLElement): ParsedContactSide | null {
  const rows: string[] = [];

  for (const node of Array.from(side.childNodes)) {
    if (node.nodeType === Node.TEXT_NODE) {
      rows.push(...splitRows(node.textContent ?? ""));
      continue;
    }

    if (!(node instanceof HTMLElement)) continue;
    const tagName = node.tagName.toLowerCase();

    if (tagName === "p") {
      rows.push(...splitRows(node.innerHTML));
      continue;
    }

    if (tagName === "br") {
      continue;
    }

    if (INLINE_ROW_TAGS.has(tagName)) {
      rows.push(...splitRows(node.outerHTML));
      continue;
    }

    return null;
  }

  const cleanedRows = rows.map(cleanRow).filter(Boolean);
  return {
    rows: cleanedRows,
    parsedRows: cleanedRows.map(parseRow),
  };
}

function splitRows(html: string): string[] {
  return html.split(BREAK_RE).map(cleanRow).filter(Boolean);
}

function cleanRow(row: string): string {
  return row.replace(/^\s+|\s+$/g, "");
}

function renderContactRow(row: string): string {
  const parsed = parseRow(row);
  const iconSlot = parsed.iconHtml
    ? `<span class="resume-contact-icon" data-contact-icon-status="${parsed.iconStatus}">${parsed.iconHtml}</span>`
    : parsed.iconStatus === "fallback"
      ? `<span class="resume-contact-icon resume-contact-icon--fallback" data-contact-icon-status="fallback" data-icon-name="${escapeAttr(parsed.iconName ?? "unknown")}" aria-hidden="true"></span>`
      : "";

  return [
    `<div class="resume-contact-row" data-contact-row-kind="${parsed.kind}">`,
    iconSlot,
    `<span class="resume-contact-text">${parsed.textHtml}</span>`,
    "</div>",
  ].join("");
}

interface ParsedRow {
  kind: "icon" | "link" | "text";
  iconStatus: "known" | "fallback" | "none";
  iconName?: string;
  iconHtml?: string;
  textHtml: string;
}

function parseRow(row: string): ParsedRow {
  const linkWithSvg = row.match(LINK_WITH_SVG_RE);
  if (linkWithSvg?.groups) {
    return {
      kind: "link",
      iconStatus: "known",
      iconHtml: linkWithSvg.groups.svg,
      textHtml: `<a${linkWithSvg.groups.attrs}>${cleanRow(linkWithSvg.groups.label)}</a>`,
    };
  }

  const linkWithIconText = row.match(LINK_WITH_ICON_TEXT_RE);
  if (linkWithIconText?.groups) {
    const iconName = linkWithIconText.groups.icon;
    const knownIcon = Object.prototype.hasOwnProperty.call(svgMap, iconName);
    return {
      kind: "link",
      iconStatus: knownIcon ? "known" : "fallback",
      iconName,
      iconHtml: knownIcon ? svgMap[iconName as keyof typeof svgMap] : undefined,
      textHtml: `<a${linkWithIconText.groups.attrs}>${cleanRow(linkWithIconText.groups.label)}</a>`,
    };
  }

  const leadingSvg = row.match(SVG_RE);
  if (leadingSvg && leadingSvg.index === 0) {
    return {
      kind: "icon",
      iconStatus: "known",
      iconHtml: leadingSvg[0],
      textHtml: cleanRow(row.slice(leadingSvg[0].length)),
    };
  }

  const plainIcon = row.match(PLAIN_ICON_RE);
  if (plainIcon?.groups) {
    const iconName = plainIcon.groups.icon;
    const knownIcon = Object.prototype.hasOwnProperty.call(svgMap, iconName);
    return {
      kind: "icon",
      iconStatus: knownIcon ? "known" : "fallback",
      iconName,
      iconHtml: knownIcon ? svgMap[iconName as keyof typeof svgMap] : undefined,
      textHtml: cleanRow(plainIcon.groups.label),
    };
  }

  return {
    kind: row.includes("<a ") ? "link" : "text",
    iconStatus: "none",
    textHtml: row,
  };
}

function isContactLikeRow(row: ParsedRow): boolean {
  return row.iconStatus !== "none";
}

function escapeAttr(value: string): string {
  return value.replace(/[&"<>]/g, (char) => {
    if (char === "&") return "&amp;";
    if (char === '"') return "&quot;";
    if (char === "<") return "&lt;";
    return "&gt;";
  });
}
