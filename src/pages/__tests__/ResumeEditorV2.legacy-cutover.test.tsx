import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
      <div data-testid="legacy-status">{data.metadata.markdown.legacyConversionStatus}</div>
      <div data-testid="legacy-warnings">
        {data.metadata.markdown.legacyConversionWarnings.join(" ")}
      </div>
    </div>
  ),
}));

function renderRoute() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/resume/legacy-1"]}>
        <Routes>
          <Route path="/resume/:id" element={<ResumeEditorV2 />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResumeEditorV2 legacy Markdown cutover", () => {
  beforeEach(() => {
    getResumeMock.mockReset();
  });

  it("hydrates structured-only resumes as Markdown with conversion status", async () => {
    getResumeMock.mockResolvedValue({
      id: "legacy-1",
      slug: "legacy-lin",
      is_public: false,
      password_set: false,
      version: 1,
      data: {
        ...defaultResumeDataV2,
        data_format_version: "v1",
        basics: {
          ...defaultResumeDataV2.basics,
          name: "Legacy Lin",
          headline: "AI Product Engineer",
          email: "legacy.lin@example.com",
        },
        summary: {
          ...defaultResumeDataV2.summary,
          content: "<p>Legacy structured summary.</p>",
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
      "Legacy structured summary.",
    );
    expect(screen.getByTestId("legacy-status")).toHaveTextContent("converted");
    expect(screen.queryByTestId("legacy-open-v1")).not.toBeInTheDocument();
  });
});
