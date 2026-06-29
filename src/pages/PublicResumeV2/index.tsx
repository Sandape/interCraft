// REQ-032 v2 — PublicResumeV2 (Batch 3).
//
// Read-only public page for a v2 resume, mounted at `/r/:username/:slug`.
// No auth required (the route lives OUTSIDE the AuthGuard in App.tsx —
// see src/App.tsx:102). State machine:
//
//   loading → ready          (success path)
//   loading → not-found     (404 from backend)
//   loading → password-required (401 with password_set)
//   loading → forbidden     (any other 4xx)
//   password-required → ready (after successful verify-password)
//
// The rendered preview reuses the same `<PreviewPane>` as the editor
// but stripped of all editing chrome (no BuilderShell, no left/right
// panels, no header). When the user clicks the browser's native
// "Print" (Ctrl/Cmd+P), the @media print block hides everything
// except the resume so print-to-paper works without leaking the
// "powered by InterCraft" footer or any controls.
//
// 2026-06-29 — First cut. The page intentionally avoids introducing
// a new design system — it borrows the styling tokens + spacing of
// the editor's preview pane so the rendered page looks identical
// to what the owner sees. The ShareDialog (for setting `is_public`)
// lives elsewhere (deferred from this batch — the public flag can be
// toggled via the ResumeList card or directly via the API).

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Loader2, Lock } from "lucide-react";
import {
  getPublicResume,
  verifyPublicPassword,
  type PublicResumeV2 as PublicResumeV2Response,
} from "@/modules/resume/v2/api";
import { PreviewPane } from "@/modules/resume/v2/editor/center/PreviewPane";
import { Button } from "@/components/ui/Button";
import type { ResumeDataV2 } from "@/modules/resume/v2/schema/data";

/**
 * Discriminated state machine — see module header for transitions.
 * `not-found` and `forbidden` look similar to the user but we keep
 * them separate so future analytics / E2E specs can distinguish a
 * missing resume from a server-permission issue.
 */
type State =
  | { kind: "loading" }
  | { kind: "not-found" }
  | { kind: "forbidden" }
  | { kind: "password-required"; resume: PublicResumeV2Response }
  | { kind: "ready"; resume: PublicResumeV2Response };

export default function PublicResumeV2() {
  const { username, slug } = useParams<{ username: string; slug: string }>();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  // Fetch on mount and whenever the route params change. We use a
  // plain effect (not React Query) because this page is single-shot
  // and never re-fetches — the user navigates away to refresh.
  useEffect(() => {
    if (!username || !slug) {
      setState({ kind: "not-found" });
      return;
    }
    let cancelled = false;
    setState({ kind: "loading" });
    getPublicResume(username, slug)
      .then((resume) => {
        if (cancelled) return;
        // 401 (password required) is thrown by the API client as an
        // `ApiError` with `code: "PASSWORD_REQUIRED"` (per backend
        // api.py:558). We don't reach this `.then` in that case.
        setState({ kind: "ready", resume });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const status =
          err && typeof err === "object" && "status" in err
            ? (err as { status?: number }).status
            : undefined;
        const code =
          err && typeof err === "object" && "code" in err
            ? (err as { code?: string }).code
            : undefined;
        if (status === 404) {
          setState({ kind: "not-found" });
          return;
        }
        if (status === 401 || code === "PASSWORD_REQUIRED") {
          // The body of the 401 doesn't include the resume metadata,
          // but we still want to render the password form. We make a
          // second `getPublicResume` call AFTER submitting the
          // password succeeds; for now, construct a placeholder.
          setState({
            kind: "password-required",
            resume: {
              id: "",
              username,
              name: "",
              slug,
              is_public: true,
              password_set: true,
              version: 0,
              updated_at: null,
              data: null,
            },
          });
          return;
        }
        setState({ kind: "forbidden" });
      });
    return () => {
      cancelled = true;
    };
  }, [username, slug]);

  const handleSubmitPassword = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      if (!username || !slug) return;
      if (!password) {
        setPasswordError("请输入密码");
        return;
      }
      setVerifying(true);
      setPasswordError(null);
      try {
        await verifyPublicPassword(username, slug, password);
        // Cookie set by the backend; refetch to get the body.
        const resume = await getPublicResume(username, slug);
        setState({ kind: "ready", resume });
        setPassword("");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "密码错误";
        setPasswordError(msg);
      } finally {
        setVerifying(false);
      }
    },
    [username, slug, password],
  );

  return (
    <div
      className="public-resume-v2 min-h-screen bg-gray-50"
      data-testid="public-resume-page"
      data-state={state.kind}
    >
      {/* Print CSS: when the user triggers the browser's Print dialog
          (Ctrl/Cmd+P), we strip every editor / page chrome and only
          keep the resume stage so the resulting PDF / paper matches
          what the owner sees in the editor. */}
      <style>{`
        @media print {
          [data-testid="public-resume-toolbar"],
          [data-testid="public-resume-footer"],
          [data-testid="public-loading"],
          [data-testid="public-not-found"],
          [data-testid="public-password-form"],
          [data-testid="public-forbidden"] {
            display: none !important;
          }
          .public-resume-v2 { background: white !important; }
          [data-testid="public-preview"] {
            padding: 0 !important;
            max-width: none !important;
          }
        }
      `}</style>

      {state.kind === "loading" && <LoadingView />}
      {state.kind === "not-found" && <NotFoundView />}
      {state.kind === "forbidden" && <ForbiddenView />}
      {state.kind === "password-required" && (
        <PasswordFormView
          password={password}
          error={passwordError}
          verifying={verifying}
          onChange={setPassword}
          onSubmit={handleSubmitPassword}
        />
      )}
      {state.kind === "ready" && (
        <ReadyView resume={state.resume} />
      )}

      <footer
        className="py-6 text-center text-[11px] text-ink-4"
        data-testid="public-resume-footer"
      >
        <Link to="/dashboard" className="hover:underline">
          由 InterCraft 生成
        </Link>
      </footer>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-views (one per state-machine branch).
// ─────────────────────────────────────────────────────────────────────────────

function LoadingView(): JSX.Element {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      data-testid="public-loading"
    >
      <Loader2 className="h-6 w-6 animate-spin text-ink-3" />
    </div>
  );
}

function NotFoundView(): JSX.Element {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center"
      data-testid="public-not-found"
    >
      <h1 className="text-lg font-semibold text-ink-1">简历不存在</h1>
      <p className="max-w-sm text-xs text-ink-3">
        这条分享链接可能已被撤销,或简历尚未公开。
      </p>
      <Link
        to="/dashboard"
        className="text-xs text-primary-500 hover:underline"
        data-testid="public-back-home"
      >
        返回首页
      </Link>
    </div>
  );
}

function ForbiddenView(): JSX.Element {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-2 p-6 text-center"
      data-testid="public-forbidden"
    >
      <h1 className="text-lg font-semibold text-ink-1">无法访问</h1>
      <p className="max-w-sm text-xs text-ink-3">
        这条分享链接当前不可用,请稍后重试。
      </p>
    </div>
  );
}

interface PasswordFormViewProps {
  password: string;
  error: string | null;
  verifying: boolean;
  onChange: (next: string) => void;
  onSubmit: (e: React.FormEvent) => Promise<void>;
}

function PasswordFormView({
  password,
  error,
  verifying,
  onChange,
  onSubmit,
}: PasswordFormViewProps): JSX.Element {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-gray-50 p-4"
      data-testid="public-password-form"
    >
      <form
        onSubmit={(e) => void onSubmit(e)}
        className="w-full max-w-sm rounded-lg border border-surface-border bg-white p-6 shadow-sm"
      >
        <div className="mb-4 flex flex-col items-center gap-2 text-center">
          <Lock className="h-7 w-7 text-ink-3" />
          <h1 className="text-base font-semibold text-ink-1">需要密码</h1>
          <p className="text-xs text-ink-3">
            该简历受密码保护,请输入密码后查看。
          </p>
        </div>
        <label
          htmlFor="public-password-input"
          className="mb-1.5 block text-xs font-medium text-ink-2"
        >
          密码
        </label>
        <input
          id="public-password-input"
          data-testid="public-password-input"
          type="password"
          value={password}
          onChange={(e) => onChange(e.target.value)}
          autoFocus
          autoComplete="current-password"
          className="w-full rounded border border-surface-border bg-transparent px-3 py-2 text-sm text-ink-1 focus:border-primary-400 focus:outline-none"
        />
        {error && (
          <p
            className="mt-2 text-xs text-rose-600"
            data-testid="public-password-error"
          >
            {error}
          </p>
        )}
        <Button
          type="submit"
          variant="primary"
          size="md"
          loading={verifying}
          disabled={verifying || !password}
          className="mt-4 w-full"
          data-testid="public-password-submit"
        >
          验证
        </Button>
      </form>
    </div>
  );
}

interface ReadyViewProps {
  resume: PublicResumeV2Response;
}

function ReadyView({ resume }: ReadyViewProps): JSX.Element {
  // The backend may return `data: null` in rare cases (e.g. race
  // condition where the resume is deleted between the password check
  // and the data fetch). We render a graceful fallback so the page
  // never crashes mid-print.
  const data: ResumeDataV2 | null = resume.data;

  return (
    <div
      className="mx-auto max-w-[820px] px-4 py-6"
      data-testid="public-preview"
    >
      <div
        className="mb-3 flex items-center justify-between text-xs text-ink-3"
        data-testid="public-resume-toolbar"
      >
        <span data-testid="public-owner-name">{resume.username || "Anonymous"}</span>
        <span data-testid="public-resume-updated">
          {resume.updated_at
            ? new Date(resume.updated_at).toLocaleDateString()
            : ""}
        </span>
      </div>
      <div className="rounded border border-surface-border bg-white shadow-sm">
        {data ? (
          <PreviewPane data={data} zoom={1} stacking="vertical" />
        ) : (
          <div
            className="p-8 text-center text-xs text-ink-3"
            data-testid="public-empty-data"
          >
            简历内容不可用。
          </div>
        )}
      </div>
    </div>
  );
}