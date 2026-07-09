// T048 — PreviewTest page (one-off).
//
// Used by T031 E2E and visual smoke checks. Renders the current
// template using sample data, and exposes a Template Gallery button
// that lets the test (or a developer) switch templates and verify
// the preview re-renders within 1s.
//
// This is a STOP-GAP for US2 visual validation only. The real
// preview lives in `src/modules/resume/v2/editor/center/PreviewPane.tsx`
// and ships with US3.

import { useState, useEffect, useMemo, Suspense } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { defaultResumeDataV2 } from "./schema/defaults";
import type { ResumeDataV2 } from "./schema/data";
import type { TemplateId } from "./schema/templates";
import { templateMap } from "./templates";
import { TemplateRoot } from "./templates/shared/TemplateRoot";
import { TemplateGallery } from "./editor/dialogs/TemplateGallery";
import { getResume, type ResumeV2 } from "./api";
import "./templates/index.css";

export default function PreviewTest() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [resume, setResume] = useState<ResumeV2 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [template, setTemplate] = useState<TemplateId>("pikachu");
  const [data, setData] = useState<ResumeDataV2>(() =>
    JSON.parse(JSON.stringify(defaultResumeDataV2))
  );
  const [galleryOpen, setGalleryOpen] = useState(false);

  // Fetch the resume by id (if provided); else use defaults.
  useEffect(() => {
    if (!id) {
      setData((d) => ({ ...d, metadata: { ...d.metadata, template } }));
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const r = await getResume(id);
        if (cancelled) return;
        setResume(r);
        const serverData = r.data as unknown as ResumeDataV2;
        setData({
          ...serverData,
          metadata: { ...serverData.metadata, template: serverData.metadata.template ?? template },
        });
        setTemplate((serverData.metadata.template as TemplateId) ?? template);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Keep `data.metadata.template` in sync with the local `template` state.
  useEffect(() => {
    setData((d) => ({
      ...d,
      metadata: { ...d.metadata, template },
    }));
  }, [template]);

  // T048 wiring: when template changes, we'd normally call the store's
  // setMetadata({ template }) which triggers debouncedSave(). The real
  // store ships in US12 (T112-T115); for US2 we just update local
  // state — the preview re-renders synchronously via the dispatcher.
  const onSelectTemplate = (nextId: TemplateId) => {
    setTemplate(nextId);
  };

  const Component = useMemo(() => templateMap[template] ?? templateMap.onyx, [template]);

  if (error) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">无法加载简历</div>
        <div className="text-xs text-ink-3">{error}</div>
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="mt-4 text-xs text-primary-500"
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen flex-col bg-surface-muted"
      data-testid="v2-editor"
      data-template={template}
    >
      <div className="flex items-center justify-between border-b border-surface-border bg-surface px-4 py-2">
        <div className="text-xs text-ink-3">
          {resume ? `${resume.name} · ${template}` : `PreviewTest · ${template}`}
        </div>
        <button
          type="button"
          data-testid="open-template-gallery"
          onClick={() => setGalleryOpen(true)}
          className="rounded-md bg-primary-500 px-3 py-1.5 text-xs text-white hover:bg-primary-600"
        >
          打开模板画廊
        </button>
      </div>
      <div className="flex flex-1 items-center justify-center overflow-auto p-6">
        <div
          className="rs-tpl-stage"
          style={{
            width: 794,
            minHeight: 1123,
            background: "white",
            boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
            borderRadius: 6,
            padding: 0,
            overflow: "hidden",
          }}
        >
          <Suspense fallback={<div className="p-8 text-sm text-ink-3">loading…</div>}>
            <Component data={data} />
          </Suspense>
        </div>
      </div>
      <TemplateGallery
        open={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        onSelect={onSelectTemplate}
        currentId={template}
      />
    </div>
  );
}
