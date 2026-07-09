/**
 * TemplateGalleryModal — used by the "new resume" flow.
 *
 * REQ-036 US4 (Phase B): the Topbar "+" → "新建简历" path opens this
 * modal. The user picks a template (or the blank option); on confirm
 * we call `createResume({ name, slug, template })` and the caller
 * navigates to the new editor. On cancel we leave the resume table
 * untouched.
 *
 * Distinct from `src/modules/resume/v2/editor/dialogs/TemplateGallery.tsx`:
 * that one is for the in-editor template switcher (mutates store
 * metadata.template). This one is the "create-from-template" flow
 * (POST /api/v1/v2/resumes).
 */
import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { createResume, type ResumeV2Create } from "@/modules/resume/v2/api";
import { fireToast } from "@/modules/resume/v2/editor/center/toast";
import { TEMPLATE_IDS, TEMPLATE_DESCRIPTORS, type TemplateId } from "@/modules/resume/v2/schema/templates";

export interface TemplateGalleryModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (input: { id: string; name: string; slug: string }) => void;
}

const BLANK_ID = "blank" as const;
type GalleryId = TemplateId | typeof BLANK_ID;

interface ManifestEntry {
  id: TemplateId;
  name: string;
  description: string;
  tags: string[];
  category: string;
  thumbnail: string;
  sidebar: "left" | "right" | "none";
  recommendedColors: { primary: string; text: string; background: string };
}

const FALLBACK_PRIMARY: Record<string, string> = {
  onyx: "rgba(0, 132, 209, 1)",
  azurill: "rgba(0, 132, 209, 1)",
  kakuna: "rgba(75, 85, 99, 1)",
  chikorita: "rgba(34, 197, 94, 1)",
  ditgar: "rgba(15, 23, 42, 1)",
  ditto: "rgba(14, 165, 233, 1)",
  bronzor: "rgba(120, 53, 15, 1)",
  pikachu: "rgba(255, 200, 55, 1)",
  lapras: "rgba(99, 102, 241, 1)",
  scizor: "rgba(220, 38, 38, 1)",
  rhyhorn: "rgba(30, 58, 138, 1)",
  glalie: "rgba(0, 132, 209, 1)",
  meowth: "rgba(245, 158, 11, 1)",
  gengar: "rgba(91, 33, 182, 1)",
  leafish: "rgba(0, 132, 209, 1)",
};

function slugify(name: string): string {
  const ascii = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return ascii || `resume-${Date.now()}`;
}

export function TemplateGalleryModal({ open, onClose, onCreated }: TemplateGalleryModalProps) {
  const [selected, setSelected] = useState<GalleryId>("pikachu");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [manifest, setManifest] = useState<Record<TemplateId, ManifestEntry> | null>(null);

  useEffect(() => {
    if (!open || manifest) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/templates/manifest.json", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { templates?: ManifestEntry[] };
        const map: Record<TemplateId, ManifestEntry> = {} as never;
        for (const t of data.templates ?? []) {
          map[t.id] = t;
        }
        if (!cancelled) setManifest(map);
      } catch {
        // Swallow — we fall back to TEMPLATE_DESCRIPTORS + FALLBACK_PRIMARY.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, manifest]);

  // Reset selection / name when modal opens fresh.
  useEffect(() => {
    if (open) {
      setSelected("pikachu");
      setName("");
      setSubmitting(false);
    }
  }, [open]);

  const orderedIds: GalleryId[] = useMemo(() => [BLANK_ID, ...TEMPLATE_IDS], []);

  async function handleConfirm() {
    if (submitting) return;
    const isBlank = selected === BLANK_ID;
    const finalName = name.trim() || (isBlank ? "未命名简历" : TEMPLATE_DESCRIPTORS[selected as TemplateId].label);
    const payload: ResumeV2Create = {
      name: finalName,
      slug: slugify(finalName),
      template: isBlank ? "onyx" : (selected as TemplateId),
      from_sample: false,
    };
    setSubmitting(true);
    try {
      const resume = await createResume(payload);
      onCreated({ id: resume.id, name: resume.name, slug: resume.slug });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "创建简历失败";
      fireToast(`创建简历失败: ${msg}`, "error");
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => !submitting && onClose()}
      title="选择模板创建简历"
      description="挑一个起点 — 模板切换后可在编辑器中再调整。"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting} data-testid="template-gallery-cancel">
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleConfirm()}
            disabled={submitting}
            leftIcon={submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : undefined}
            data-testid="template-gallery-confirm"
          >
            {submitting ? "创建中…" : "使用此模板创建"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5" data-testid="template-gallery-grid">
          {orderedIds.map((id) => {
            const isBlank = id === BLANK_ID;
            const templateId = id as TemplateId;
            const desc = isBlank
              ? { id: BLANK_ID, label: "空白模板", description: "从一个干净的画布开始" }
              : TEMPLATE_DESCRIPTORS[templateId];
            const primary = isBlank ? "rgba(229, 231, 235, 1)" : FALLBACK_PRIMARY[templateId];
            const thumb = isBlank ? null : `/templates/jpg/${templateId}.jpg`;
            const isSelected = selected === id;
            return (
              <button
                key={id}
                type="button"
                data-testid={`template-thumbnail-${id}`}
                onClick={() => setSelected(id)}
                className={[
                  "group flex flex-col gap-2 rounded-md border p-2 text-left transition",
                  isSelected
                    ? "border-primary-500 ring-2 ring-primary-200"
                    : "border-surface-border hover:border-primary-300",
                ].join(" ")}
              >
                <div
                  className="aspect-[400/565] w-full overflow-hidden rounded-sm flex items-center justify-center"
                  style={{ background: primary }}
                >
                  {isBlank ? (
                    <Plus className="h-8 w-8 text-white/70" strokeWidth={1.5} />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={thumb!}
                      alt={desc.label}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  )}
                </div>
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-ink-1">{desc.label}</span>
                    {isSelected && (
                      <span className="rounded bg-primary-100 px-1.5 py-0.5 text-[10px] text-primary-700">
                        当前
                      </span>
                    )}
                  </div>
                  <p className="line-clamp-2 text-xs text-ink-3">{desc.description}</p>
                </div>
              </button>
            );
          })}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="template-gallery-name" className="text-xs text-ink-3">
            简历名称
          </label>
          <input
            id="template-gallery-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={selected === BLANK_ID ? "未命名简历" : TEMPLATE_DESCRIPTORS[selected as TemplateId].label}
            maxLength={80}
            data-testid="template-gallery-name"
            className="w-full h-9 px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface transition-all"
          />
        </div>
      </div>
    </Modal>
  );
}
