// T096 — Summary editor (uses <RichTextEditor>) for `data.summary.content`.
//
// Wires the rich text editor to the Zustand store's `setData` action so
// edits to the summary content are persisted to the resume document.

import { useCallback } from "react";
import { useResumeV2Store } from "../../store";
import { RichTextEditor } from "../dialogs/RichTextEditor";

export function SummaryEditor() {
  const data = useResumeV2Store((s) => s.data);
  const setData = useResumeV2Store((s) => s.setData);
  const locale = data.metadata.page.locale;

  const handleChange = useCallback(
    (html: string) => {
      setData({ ...data, summary: { ...data.summary, content: html } });
    },
    [data, setData],
  );

  return (
    <div data-testid="summary-editor" className="space-y-1">
      <label className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">
        Summary
      </label>
      <RichTextEditor
        value={data.summary.content}
        onChange={handleChange}
        locale={locale}
        placeholder="A short professional summary…"
      />
    </div>
  );
}
