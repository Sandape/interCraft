// T047 — Template Gallery modal.
//
// Displays the 10 v2 templates as a 4-column grid of cards. Each card
// shows a thumbnail + name + 3-5 tags. Click a card → calls
// `onSelect(id)` and the caller (editor) updates the store's
// `metadata.template`, which triggers the live preview re-render.
//
// Click backdrop or press ESC → onClose().

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/Modal";
import type { TemplateId } from "../../schema/templates";
import { TEMPLATE_IDS } from "../../schema/templates";

export interface TemplateGalleryProps {
  open: boolean;
  onClose: () => void;
  onSelect: (id: TemplateId) => void;
  /** Current template id — used to mark the active card. */
  currentId?: TemplateId;
}

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

const FALLBACK_DESCRIPTION: Record<TemplateId, string> = {
  onyx: "极简纯文本风格。",
  azurill: "左 sidebar + 右 main 商务风格。",
  kakuna: "居中对称极简风格。",
  chikorita: "右实色 sidebar 反相文字。",
  ditgar: "左 tint sidebar + 2px item 竖线。",
  bronzor: "行式 section 商务风格。",
  pikachu: "彩色 header 卡片 + 左 sidebar。",
  lapras: "圆角卡片 + 浮动 section 标题。",
  scizor: "杂志风 letterhead。",
  rhyhorn: "管道分隔 contact 商务风。",
};

const FALLBACK_TAGS: Record<TemplateId, string[]> = {
  onyx: ["Minimal", "ATS", "Tech"],
  azurill: ["Two-column", "Business", "Sidebar"],
  kakuna: ["Minimal", "Centered", "Academic"],
  chikorita: ["Right-sidebar", "Creative", "Design"],
  ditgar: ["Tech", "Sidebar", "Engineer"],
  bronzor: ["Row-style", "Business", "Compact"],
  pikachu: ["Two-column", "Creative", "Visual flair"],
  lapras: ["Card", "Rounded", "Product"],
  scizor: ["Editorial", "Letterhead", "Magazine"],
  rhyhorn: ["Business", "Pipe", "Finance"],
};

const FALLBACK_PRIMARY: Record<TemplateId, string> = {
  onyx: "rgba(0, 132, 209, 1)",
  azurill: "rgba(0, 132, 209, 1)",
  kakuna: "rgba(75, 85, 99, 1)",
  chikorita: "rgba(34, 197, 94, 1)",
  ditgar: "rgba(15, 23, 42, 1)",
  bronzor: "rgba(120, 53, 15, 1)",
  pikachu: "rgba(255, 200, 55, 1)",
  lapras: "rgba(99, 102, 241, 1)",
  scizor: "rgba(220, 38, 38, 1)",
  rhyhorn: "rgba(30, 58, 138, 1)",
};

export function TemplateGallery({
  open,
  onClose,
  onSelect,
  currentId,
}: TemplateGalleryProps) {
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
        // Swallow — we fall back to the static FALLBACK_* maps.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, manifest]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="选择模板"
      description="10 套精选模板，点击切换预览。模板切换不修改数据。"
      size="lg"
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-template-gallery>
        {TEMPLATE_IDS.map((id) => {
          const m = manifest?.[id];
          const tags = m?.tags ?? FALLBACK_TAGS[id];
          const description = m?.description ?? FALLBACK_DESCRIPTION[id];
          const thumb = m?.thumbnail ?? `/templates/jpg/${id}.jpg`;
          const primary = m?.recommendedColors?.primary ?? FALLBACK_PRIMARY[id];
          return (
            <button
              key={id}
              type="button"
              data-testid="template-card"
              data-template={id}
              data-template-id={id}
              onClick={() => {
                onSelect(id);
                onClose();
              }}
              className={[
                "group flex flex-col gap-2 rounded-md border p-2 text-left transition",
                currentId === id
                  ? "border-primary-500 ring-2 ring-primary-200"
                  : "border-surface-border hover:border-primary-300",
              ].join(" ")}
              style={{ ["--card-primary" as string]: primary }}
            >
              <div
                className="aspect-[400/565] w-full overflow-hidden rounded-sm"
                style={{ background: primary }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={thumb}
                  alt={m?.name ?? id}
                  className="h-full w-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    // Hide broken thumbnail gracefully.
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink-1">
                    {m?.name ?? id}
                  </span>
                  {currentId === id && (
                    <span className="rounded bg-primary-100 px-1.5 py-0.5 text-[10px] text-primary-700">
                      当前
                    </span>
                  )}
                </div>
                <p className="line-clamp-2 text-xs text-ink-3">{description}</p>
                <div className="flex flex-wrap gap-1">
                  {tags.slice(0, 5).map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] text-ink-3"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </Modal>
  );
}
