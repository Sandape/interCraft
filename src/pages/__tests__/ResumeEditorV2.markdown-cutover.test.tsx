import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { defaultResumeDataV2 } from "@/modules/resume/v2/schema/defaults";
import ResumeEditorV2 from "../ResumeEditorV2";

const getResumeMock = vi.fn();

vi.mock("@/modules/resume/v2/api", () => ({
  getResume: (...args: unknown[]) => getResumeMock(...args),
  updateResume: vi.fn(),
}));

vi.mock("@/modules/resume/v2/hooks/useResumeSse", () => ({
  useResumeSse: vi.fn(),
}));

vi.mock("@/modules/resume/v2/editor/center/toast", () => ({
  fireToast: vi.fn(),
}));

vi.mock("@/modules/resume/v2/editor/BuilderShell", () => ({
  BuilderShell: ({ data }: { data: typeof defaultResumeDataV2 }) => (
    <div data-testid="builder-shell-probe">
      <textarea
        readOnly
        data-testid="markdown-source-editor"
        value={data.metadata.markdown.sourceMarkdown}
      />
      <div data-testid="markdown-theme">{data.metadata.markdown.themeId}</div>
      <div data-testid="legacy-status">{data.metadata.markdown.legacyConversionStatus}</div>
    </div>
  ),
}));

function renderRoute() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/resume/r1"]}>
        <Routes>
          <Route path="/resume/:id" element={<ResumeEditorV2 />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResumeEditorV2 Markdown cutover", () => {
  it("hydrates existing Markdown source and settings", async () => {
    getResumeMock.mockResolvedValue({
      id: "r1",
      slug: "lin",
      is_public: false,
      password_set: false,
      version: 1,
      data: {
        ...defaultResumeDataV2,
        metadata: {
          ...defaultResumeDataV2.metadata,
          markdown: {
            ...defaultResumeDataV2.metadata.markdown,
            sourceMarkdown: "# Existing Markdown",
            themeId: "muji-minimal-color",
          },
        },
      },
    });

    renderRoute();

    await waitFor(() =>
      expect(screen.getByTestId("markdown-source-editor")).toHaveValue("# Existing Markdown"),
    );
    expect(screen.getByTestId("markdown-theme")).toHaveTextContent("muji-minimal-color");
  });

  it("converts structured-only data into Markdown instead of rendering a legacy escape hatch", async () => {
    getResumeMock.mockResolvedValue({
      id: "r1",
      slug: "legacy",
      is_public: false,
      password_set: false,
      version: 1,
      data: {
        ...defaultResumeDataV2,
        data_format_version: "v1",
        basics: {
          ...defaultResumeDataV2.basics,
          name: "Legacy Lin",
          email: "legacy@example.com",
        },
        summary: {
          ...defaultResumeDataV2.summary,
          content: "<p>Legacy summary.</p>",
        },
        metadata: {
          ...defaultResumeDataV2.metadata,
          markdown: {
            ...defaultResumeDataV2.metadata.markdown,
            sourceMarkdown: "",
          },
        },
      },
    });

    renderRoute();

    await waitFor(() =>
      expect((screen.getByTestId("markdown-source-editor") as HTMLTextAreaElement).value).toContain(
        "# Legacy Lin",
      ),
    );
    expect((screen.getByTestId("markdown-source-editor") as HTMLTextAreaElement).value).toContain(
      "legacy@example.com",
    );
    expect(screen.queryByTestId("legacy-open-v1")).not.toBeInTheDocument();
  });
});
