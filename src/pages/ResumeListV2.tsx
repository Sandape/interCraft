/**
 * ResumeListV2 — T159 (US16).
 *
 * Lists the current user's v2 resumes. Each card shows the resume
 * name, slug, is_public badge, and last-updated timestamp. A
 * "Duplicate" button calls `duplicateResume(id)` and navigates to the
 * new editor; an "Open" button navigates to the existing editor.
 *
 * The page is read-mostly: the resume list comes from
 * `listResumes()` (no data blob per the §1.1 list contract).
 */
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Copy,
  Eye,
  EyeOff,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
} from "lucide-react";
import {
  createResume,
  duplicateResume,
  listResumes,
  type ResumeV2ListItem,
} from "@/modules/resume/v2/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { timeAgo } from "@/lib/utils";

function PublicBadge({ isPublic }: { isPublic: boolean }): JSX.Element {
  if (isPublic) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700"
        data-testid="resume-card-public"
      >
        <Eye className="h-3 w-3" /> Public
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded bg-surface-muted px-1.5 py-0.5 text-[10px] text-ink-3"
      data-testid="resume-card-private"
    >
      <EyeOff className="h-3 w-3" /> Private
    </span>
  );
}

interface CardProps {
  resume: ResumeV2ListItem;
  onDuplicate: (id: string) => Promise<void>;
  onOpen: (id: string) => void;
  duplicating: boolean;
}

function ResumeCard({ resume, onDuplicate, onOpen, duplicating }: CardProps): JSX.Element {
  return (
    <article
      data-testid="v2-resume-card"
      data-resume-id={resume.id}
      className="flex flex-col gap-2 rounded border border-surface-border bg-white p-3"
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-1">{resume.name}</h3>
          <p className="text-[10px] text-ink-3">/{resume.slug}</p>
        </div>
        <PublicBadge isPublic={resume.is_public} />
      </header>
      <div className="flex items-center justify-between text-[10px] text-ink-3">
        <span>v{resume.version}</span>
        <span>updated {resume.updated_at ? timeAgo(resume.updated_at) : "—"}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="primary"
          onClick={() => onOpen(resume.id)}
          data-testid="resume-card-open"
        >
          <Pencil className="h-3 w-3" />
          Open
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void onDuplicate(resume.id)}
          disabled={duplicating}
          data-testid="resume-card-duplicate"
        >
          {duplicating ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          Duplicate
        </Button>
      </div>
    </article>
  );
}

export default function ResumeListV2(): JSX.Element {
  const qc = useQueryClient();
  const [duplicating, setDuplicating] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(
    () => searchParams.get("new") === "true",
  );
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["resumes-v2-list"],
    queryFn: () => listResumes({ sort: "updated" }),
  });

  function closeCreate() {
    setCreateOpen(false);
    setNewName("");
    setNewSlug("");
    setCreateError(null);
    if (searchParams.get("new")) {
      const next = new URLSearchParams(searchParams);
      next.delete("new");
      setSearchParams(next, { replace: true });
    }
  }

  async function handleCreate() {
    const name = newName.trim();
    const slug =
      newSlug.trim() ||
      name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") ||
      "untitled";
    if (!name) return;
    setCreating(true);
    setCreateError(null);
    try {
      const r = await createResume({ name, slug, from_sample: true });
      await qc.invalidateQueries({ queryKey: ["resumes-v2-list"] });
      if (typeof window !== "undefined") {
        window.location.assign(`/resume/v2/${r.id}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "创建失败";
      setCreateError(msg);
      setCreating(false);
    }
  }

  const handleDuplicate = async (id: string) => {
    if (duplicating) return;
    setDuplicating(true);
    try {
      const copy = await duplicateResume(id);
      await qc.invalidateQueries({ queryKey: ["resumes-v2-list"] });
      if (typeof window !== "undefined") {
        window.location.assign(`/resume/v2/${copy.id}`);
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("Duplicate failed:", err);
    } finally {
      setDuplicating(false);
    }
  };

  const handleOpen = (id: string) => {
    if (typeof window !== "undefined") {
      window.location.assign(`/resume/v2/${id}`);
    }
  };

  return (
    <div
      className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4"
      data-testid="resume-list-v2"
    >
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-ink-1">v2 Resumes</h1>
          <p className="text-[11px] text-ink-3">
            New structured editor with auto-save, sharing and AI analysis.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            data-testid="resume-list-new-link"
            className="inline-flex h-8 items-center gap-1 rounded bg-brand px-3 text-xs font-medium text-white hover:bg-brand/90"
          >
            <Plus className="h-3.5 w-3.5" />
            New v2 Resume
          </button>
        </div>
      </header>

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-ink-3" data-testid="resume-list-loading">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading…
        </div>
      )}

      {error && (
        <div className="rounded border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
          Failed to load resumes.{" "}
          <button
            type="button"
            onClick={() => void refetch()}
            className="underline"
          >
            Retry
          </button>
        </div>
      )}

      {data && data.data.length === 0 && (
        <div
          className="rounded border border-dashed border-surface-border bg-white p-6 text-center"
          data-testid="resume-list-empty"
        >
          <Sparkles className="mx-auto mb-2 h-6 w-6 text-ink-3" />
          <p className="text-sm text-ink-2">No v2 resumes yet.</p>
          <p className="text-[11px] text-ink-3">
            Create one to get started with the structured editor.
          </p>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            data-testid="resume-list-empty-create"
            className="mt-3 inline-flex h-8 items-center gap-1 rounded bg-brand px-3 text-xs font-medium text-white hover:bg-brand/90"
          >
            <Plus className="h-3.5 w-3.5" />
            New v2 Resume
          </button>
        </div>
      )}

      {data && data.data.length > 0 && (
        <div
          className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3"
          data-testid="resume-list-grid"
        >
          {data.data.map((r) => (
            <ResumeCard
              key={r.id}
              resume={r}
              onDuplicate={handleDuplicate}
              onOpen={handleOpen}
              duplicating={duplicating}
            />
          ))}
        </div>
      )}

      <Modal
        open={createOpen}
        onClose={closeCreate}
        title="新建 v2 简历"
        description="使用结构化编辑器快速生成可定制模板"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={closeCreate} disabled={creating}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={!newName.trim() || creating}
              onClick={handleCreate}
              data-testid="v2-create-confirm"
            >
              {creating ? "创建中…" : "创建"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">
              简历名称
            </label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例如：字节前端 v2"
              data-testid="v2-create-name"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">
              Slug（可选，留空自动生成）
            </label>
            <Input
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value)}
              placeholder="bytedance-frontend"
            />
          </div>
          {createError && (
            <p className="text-xs text-red-500" data-testid="v2-create-error">
              {createError}
            </p>
          )}
        </div>
      </Modal>
    </div>
  );
}
