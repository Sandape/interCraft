import type { LineHeightPreset } from "@/modules/resume/renderer/types";

export type PageBreakReason =
  | "page_full"
  | "avoid_orphan_heading"
  | "keep_table_readable"
  | "keep_list_readable"
  | "oversized_block"
  | "fallback";

export interface ResumePreviewPage {
  pageIndex: number;
  pageNumber: number;
  html: string;
  breakBeforeBlockId: string | null;
  breakAfterBlockId: string | null;
}

export interface PageBreakDecision {
  beforeNodeKey: string | null;
  afterNodeKey: string | null;
  reason: PageBreakReason;
  warnings: string[];
}

export interface PaginatedResumePreview {
  pages: ResumePreviewPage[];
  pageCount: number;
  lineHeight: LineHeightPreset;
  renderVersion: string;
  overflowWarnings: string[];
  breaks: PageBreakDecision[];
}
