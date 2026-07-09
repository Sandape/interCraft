import type { LegacyConversionStatus } from "@/modules/resume/renderer/types";

export interface LegacyConversionResult {
  status: LegacyConversionStatus;
  convertedMarkdown: string;
  warnings: string[];
}

type LegacyRecord = Record<string, unknown>;

export function convertLegacyResumeToMarkdown(input: unknown): LegacyConversionResult {
  const data = asRecord(input);
  const existing = getString(asRecord(asRecord(data.metadata).markdown).sourceMarkdown);
  if (existing.trim()) {
    return { status: "not_needed", convertedMarkdown: existing, warnings: [] };
  }

  const warnings: string[] = [];
  const lines: string[] = [];
  const basics = asRecord(data.basics);
  const name = getString(basics.name) || "Untitled Resume";
  lines.push(`# ${name}`);

  const headline = getString(basics.headline);
  if (headline) lines.push("", headline);

  const contactLines = contactMarkdown(basics);
  if (contactLines.length > 0) {
    lines.push("", "::: left", ...contactLines, ":::");
  }

  const summary = asRecord(data.summary);
  if (!isHidden(summary)) {
    const summaryText = stripHtml(getString(summary.content));
    if (summaryText) {
      lines.push("", `## ${getString(summary.title) || "Summary"}`, "", summaryText);
    }
  }

  const sections = asRecord(data.sections);
  for (const [key, value] of Object.entries(sections)) {
    const section = asRecord(value);
    if (isHidden(section)) continue;
    const rendered = renderSection(getString(section.title) || titleize(key), section);
    if (rendered.length > 0) lines.push("", ...rendered);
  }

  const customSections = Array.isArray(data.customSections) ? data.customSections : [];
  for (const custom of customSections) {
    const section = asRecord(custom);
    if (isHidden(section)) continue;
    const rendered = renderSection(getString(section.title) || "Custom Section", section);
    if (rendered.length > 0) {
      lines.push("", ...rendered);
    }
  }

  const markdown = lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  return {
    status: warnings.length > 0 ? "warning" : "converted",
    convertedMarkdown: markdown,
    warnings,
  };
}

function contactMarkdown(basics: LegacyRecord): string[] {
  const rows: string[] = [];
  const phone = getString(basics.phone);
  const email = getString(basics.email);
  const location = getString(basics.location);
  const website = asRecord(basics.website);
  if (phone) rows.push(`icon:phone ${phone}`);
  if (email) rows.push(`icon:email ${email}`);
  if (location) rows.push(`icon:location ${location}`);
  const websiteUrl = getString(website.url);
  if (websiteUrl) {
    const label = getString(website.label) || websiteUrl;
    rows.push(`[icon:link ${label}](${websiteUrl})`);
  }
  const customFields = Array.isArray(basics.customFields) ? basics.customFields : [];
  for (const field of customFields) {
    const record = asRecord(field);
    const label = getString(record.name) || "Contact";
    const value = getString(record.value);
    if (value) rows.push(`${label}: ${value}`);
  }
  return rows;
}

function renderSection(title: string, section: LegacyRecord): string[] {
  const items = Array.isArray(section.items) ? section.items.map(asRecord) : [];
  const content = stripHtml(getString(section.content));
  const lines: string[] = [`## ${title}`];
  if (content) lines.push("", content);
  for (const item of items) {
    const rendered = renderItem(item);
    if (rendered.length > 0) lines.push("", ...rendered);
  }
  return lines.length > 1 ? lines : [];
}

function renderItem(item: LegacyRecord): string[] {
  const title =
    getString(item.name) ||
    getString(item.position) ||
    getString(item.company) ||
    getString(item.institution) ||
    getString(item.area) ||
    getString(item.title);
  const subtitle = [item.company, item.institution, item.area]
    .map(getString)
    .filter(Boolean)
    .filter((value) => value !== title)
    .join(" - ");
  const date = getString(item.date) || getString(item.period);
  const description =
    stripHtml(getString(item.summary)) ||
    stripHtml(getString(item.description)) ||
    stripHtml(getString(item.content));
  const keywords = Array.isArray(item.keywords) ? item.keywords.map(getString).filter(Boolean) : [];

  const lines: string[] = [];
  if (title) lines.push(`### ${title}`);
  if (subtitle || date) lines.push([subtitle, date].filter(Boolean).join(" | "));
  if (description) lines.push("", description);
  if (keywords.length > 0) lines.push("", `- ${keywords.join(", ")}`);
  return lines.filter((line, index, array) => line !== "" || array[index - 1] !== "");
}

function asRecord(value: unknown): LegacyRecord {
  return value && typeof value === "object" ? (value as LegacyRecord) : {};
}

function getString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isHidden(value: LegacyRecord): boolean {
  return value.hidden === true;
}

function stripHtml(value: string): string {
  return value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>\s*<p>/gi, "\n\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();
}

function titleize(value: string): string {
  return value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
