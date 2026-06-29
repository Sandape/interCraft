// REQ-034 US1 — DialogHost (single dispatcher for v2 content dialogs).
//
// Centralizes the open/close state and routes the active dialog type to the
// matching React component. New content dialogs (US2..US6) should be added
// to the switch statement in `<DialogHost>` below; consumers call
// `useDialogStore.getState().openDialog({ type: "basics" })` etc.
//
// Notes (per AC-11b):
//   - US1 basics / picture are SINGLE-instance editors (no create vs.
//     update distinction). The `type` namespace is therefore the bare
//     section name: `'basics' | 'picture'`. Verb-suffixed namespaces
//     (`'experience.create'` etc.) will be introduced as US2 adds
//     per-item dialogs.
//   - DELETE actions live inline in the calling UI (e.g. customField ×
//     button) and do NOT route through this dispatcher.
//
// File naming: see L008 (module shadow trap). Filename is `DialogHost.tsx`
// — there is no sibling `DialogHost.ts` or `dialogs/DialogHost/index.ts`.

import { useEffect, useRef } from "react";
import { create } from "zustand";
import { BasicsDialog } from "./BasicsDialog";
import { PictureDialog } from "./PictureDialog";
import { ExperienceDialog } from "./ExperienceDialog";
import { EducationDialog } from "./EducationDialog";
import { ProjectsDialog } from "./ProjectsDialog";
import { SkillsDialog } from "./SkillsDialog";
import { useResumeV2Store } from "../../store";

// ── type namespace ─────────────────────────────────────────────────────────

/**
 * Dialog types dispatched by `DialogHost`.
 *
 * Today:
 *   - `'basics' | 'picture'` (US1, single-instance editors — bare section
 *     name, no verb suffix).
 *   - `'experience.create' | 'experience.update'` (US2, per-item editors
 *     — `{section}.{verb}` shape).
 *   - `'education.{create,update}' | 'projects.{create,update}' | 'skills.{create,update}'`
 *     (US3, per-item editors — same `{section}.{verb}` shape). Delete
 *     actions live inline and do NOT route through this dispatcher.
 */
export type DialogType =
  | "basics"
  | "picture"
  | "experience.create"
  | "experience.update"
  | "education.create"
  | "education.update"
  | "projects.create"
  | "projects.update"
  | "skills.create"
  | "skills.update";

export interface ExperienceUpdatePayload {
  sectionId: string;
  itemId: string;
}

export interface DialogSpec {
  type: DialogType;
  /**
   * Per-dialog payload:
   *   - `'basics' | 'picture'`: undefined.
   *   - `'*.create'`: `{ sectionId: string }`.
   *   - `'*.update'`: `{ sectionId: string, itemId: string }`.
   */
  payload?: ExperienceUpdatePayload | { sectionId: string };
}

interface DialogState {
  active: DialogSpec | null;
  openDialog: (spec: DialogSpec) => void;
  closeDialog: () => void;
}

export const useDialogStore = create<DialogState>((set) => ({
  active: null,
  openDialog: (spec) => set({ active: spec }),
  closeDialog: () => set({ active: null }),
}));

// ── component ──────────────────────────────────────────────────────────────

/**
 * Mounts a single active dialog at a time. Consumers typically render
 * `<DialogHost />` once near the root of the v2 editor (BuilderShell body).
 *
 * Cancel-on-close contract (AC-08b / AC-08c):
 *   When the dialog closes (ESC / backdrop / Cancel), we treat the close
 *   as a CANCEL — every `setDataMut` that fired during this dialog's
 *   lifetime is rolled back via `undo()`. The store's pending 500ms
 *   debounce is then a no-op for the cancelled mutations because the
 *   data reverted to the pre-dialog snapshot.
 */
export function DialogHost(): JSX.Element | null {
  const active = useDialogStore((s) => s.active);
  const closeDialog = useDialogStore((s) => s.closeDialog);
  const undoStackDepthAtOpen = useRef(0);
  const undo = useResumeV2Store((s) => s.undo);

  // When a dialog opens, snapshot the undo-stack depth so close() knows
  // how many mutations to roll back.
  useEffect(() => {
    if (active) {
      undoStackDepthAtOpen.current = useResumeV2Store.getState().undoStack.length;
    }
  }, [active]);

  const handleClose = () => {
    const depthNow = useResumeV2Store.getState().undoStack.length;
    const rollbackCount = depthNow - undoStackDepthAtOpen.current;
    for (let i = 0; i < rollbackCount; i++) {
      undo();
    }
    closeDialog();
  };

  // Belt + suspenders: ESC on the global keydown listener mirrors the
  // Modal component's own ESC handling so the dialog still closes if the
  // Modal listener is ever removed. AC-08 / AC-08b rely on ESC closing.
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  if (!active) return null;
  switch (active.type) {
    case "basics":
      return <BasicsDialog onClose={handleClose} />;
    case "picture":
      return <PictureDialog onClose={handleClose} />;
    case "experience.create": {
      const sectionId =
        (active.payload as { sectionId?: string } | undefined)?.sectionId ??
        "experience";
      return <ExperienceDialog onClose={handleClose} sectionId={sectionId} itemId="" />;
    }
    case "experience.update": {
      const payload = active.payload as
        | { sectionId?: string; itemId?: string }
        | undefined;
      const sectionId = payload?.sectionId ?? "experience";
      const itemId = payload?.itemId ?? "";
      return (
        <ExperienceDialog
          onClose={handleClose}
          sectionId={sectionId}
          itemId={itemId}
        />
      );
    }
    case "education.create": {
      const sectionId =
        (active.payload as { sectionId?: string } | undefined)?.sectionId ??
        "education";
      return <EducationDialog onClose={handleClose} sectionId={sectionId} itemId="" />;
    }
    case "education.update": {
      const payload = active.payload as
        | { sectionId?: string; itemId?: string }
        | undefined;
      const sectionId = payload?.sectionId ?? "education";
      const itemId = payload?.itemId ?? "";
      return (
        <EducationDialog
          onClose={handleClose}
          sectionId={sectionId}
          itemId={itemId}
        />
      );
    }
    case "projects.create": {
      const sectionId =
        (active.payload as { sectionId?: string } | undefined)?.sectionId ??
        "projects";
      return <ProjectsDialog onClose={handleClose} sectionId={sectionId} itemId="" />;
    }
    case "projects.update": {
      const payload = active.payload as
        | { sectionId?: string; itemId?: string }
        | undefined;
      const sectionId = payload?.sectionId ?? "projects";
      const itemId = payload?.itemId ?? "";
      return (
        <ProjectsDialog
          onClose={handleClose}
          sectionId={sectionId}
          itemId={itemId}
        />
      );
    }
    case "skills.create": {
      const sectionId =
        (active.payload as { sectionId?: string } | undefined)?.sectionId ??
        "skills";
      return <SkillsDialog onClose={handleClose} sectionId={sectionId} itemId="" />;
    }
    case "skills.update": {
      const payload = active.payload as
        | { sectionId?: string; itemId?: string }
        | undefined;
      const sectionId = payload?.sectionId ?? "skills";
      const itemId = payload?.itemId ?? "";
      return (
        <SkillsDialog
          onClose={handleClose}
          sectionId={sectionId}
          itemId={itemId}
        />
      );
    }
    default: {
      // Fail loud (AC-11b-revised): an unknown type means a new verb
      // was added without extending this switch. Silent `return null`
      // would result in a black-screen dialog in production. We throw
      // so the failure surfaces immediately in dev/test.
      const unknown = (active as { type: string }).type;
      throw new Error(`unknown dialog type: ${unknown}`);
    }
  }
}

export default DialogHost;