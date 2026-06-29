// REQ-034 US3 — SectionItem shared wrapper tests.
//
// Covers AC-04c/05c/06c (hidden=true visual fade), AC-19 (single
// SectionItem path, named export), and confirms the three SectionLists
// all `import { SectionItem }` from this same file (R13).

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import React from "react";
import { DndContext, closestCenter } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";

afterEach(() => cleanup());

// Wrap the row in a DndContext + SortableContext so useSortable() can
// find an ancestor provider in jsdom (otherwise it throws).
function WithProviders({ children }: { children: React.ReactNode }) {
  return (
    <DndContext collisionDetection={closestCenter}>
      <SortableContext items={["x1"]} strategy={verticalListSortingStrategy}>
        {children}
      </SortableContext>
    </DndContext>
  );
}

describe("SectionItem wrapper (AC-04c/05c/06c, AC-19)", () => {
  it("renders title + subtitle + 3 inline actions", async () => {
    const { SectionItem } = await import("../SectionItem");
    render(
      <WithProviders>
        <SectionItem
          id="x1"
          hidden={false}
          sectionKey="education"
          title="Tsinghua"
          subtitle="Bachelor"
          onEdit={() => {}}
          onDuplicate={() => {}}
          onDelete={() => {}}
        />
      </WithProviders>,
    );
    expect(screen.getByTestId("education-item-row-x1")).toBeTruthy();
    expect(screen.getByTestId("education-item-edit-x1")).toBeTruthy();
    expect(screen.getByTestId("education-item-duplicate-x1")).toBeTruthy();
    expect(screen.getByTestId("education-item-delete-x1")).toBeTruthy();
    // default fallback testid is `${sectionKey}-name-display`
    expect(screen.getByTestId("education-name-display").textContent).toBe("Tsinghua");
  });

  it("hidden=true renders row with data-hidden=true (AC-04c/05c/06c)", async () => {
    const { SectionItem } = await import("../SectionItem");
    render(
      <WithProviders>
        <SectionItem
          id="x2"
          hidden={true}
          sectionKey="projects"
          title="MyProj"
          subtitle="2024"
          onEdit={() => {}}
          onDuplicate={() => {}}
          onDelete={() => {}}
        />
      </WithProviders>,
    );
    const row = screen.getByTestId("projects-item-row-x2") as HTMLElement;
    expect(row.getAttribute("data-hidden")).toBe("true");
    // AC-04c/05c/06c: text content is still rendered, just faded.
    expect(row.textContent).toContain("MyProj");
  });

  it("edit/duplicate/delete buttons fire callbacks (AC-17)", async () => {
    const onEdit = (id: string) => {
      (globalThis as Record<string, unknown>).__edit = id;
    };
    const onDup = (id: string) => {
      (globalThis as Record<string, unknown>).__dup = id;
    };
    const onDel = (id: string) => {
      (globalThis as Record<string, unknown>).__del = id;
    };
    const { SectionItem } = await import("../SectionItem");
    render(
      <WithProviders>
        <SectionItem
          id="x3"
          hidden={false}
          sectionKey="skills"
          title="React"
          subtitle="Fluent"
          onEdit={onEdit}
          onDuplicate={onDup}
          onDelete={onDel}
        />
      </WithProviders>,
    );
    fireEvent.click(screen.getByTestId("skills-item-edit-x3"));
    fireEvent.click(screen.getByTestId("skills-item-duplicate-x3"));
    fireEvent.click(screen.getByTestId("skills-item-delete-x3"));
    expect((globalThis as { __edit?: string }).__edit).toBe("x3");
    expect((globalThis as { __dup?: string }).__dup).toBe("x3");
    expect((globalThis as { __del?: string }).__del).toBe("x3");
  });

  it("path uniqueness: only one SectionItem.tsx exists in src (R13)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    function walk(dir: string): string[] {
      const out: string[] = [];
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (
            entry.name === "node_modules" ||
            entry.name === ".git" ||
            entry.name === "dist" ||
            entry.name === "build"
          )
            continue;
          out.push(...walk(full));
        } else if (entry.name === "SectionItem.tsx") {
          out.push(full);
        }
      }
      return out;
    }
    const hits = walk(path.join(process.cwd(), "src"));
    expect(hits.length).toBe(1);
    expect(hits[0]).toMatch(/left[\/\\]SectionItem\.tsx$/);
  });

  it("named export: 3 SectionLists import from same path (R7, AC-01)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const files = [
      "EducationSectionList.tsx",
      "ProjectsSectionList.tsx",
      "SkillsSectionList.tsx",
    ];
    const imports = files.map((f) => {
      const p = path.join(
        process.cwd(),
        "src/modules/resume/v2/editor/left",
        f,
      );
      return fs.readFileSync(p, "utf-8");
    });
    for (const src of imports) {
      expect(src).toMatch(/import\s*\{\s*SectionItem\s*\}\s*from\s*"\.\/SectionItem"/);
    }
  });
});