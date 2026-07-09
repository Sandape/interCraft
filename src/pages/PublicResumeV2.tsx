// T146 — Public resume page (US11).
//
// Route: /r/:username/:slug
//
// - No auth required.
// - Renders the template via the same `templateMap` the editor uses
//   (read-only — no edit affordances).
// - Injects `<meta name="robots" content="noindex, follow">` per FR-080
//   so search engines do not index public resumes.
// - If password-protected and no valid cookie: shows a password form;
//   on submit POSTs /verify-password then re-fetches.

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams, Link } from "react-router-dom";
import { Eye, EyeOff, Loader2, Lock } from "lucide-react";
import {
  getPublicResume,
  verifyPublicPassword,
  type PublicResumeV2 as PublicResumeV2Dto,
} from "@/modules/resume/v2/api";
import { templateMap } from "@/modules/resume/v2/templates";
import { defaultResumeDataV2 } from "@/modules/resume/v2/schema/defaults";
import type { ResumeDataV2 } from "@/modules/resume/v2/schema/data";

interface PublicState {
  resume: PublicResumeV2Dto | null;
  passwordRequired: boolean;
  loading: boolean;
  error: string | null;
}

export default function PublicResumeV2() {
  const { username = "", slug = "" } = useParams<{ username: string; slug: string }>();
  const [state, setState] = useState<PublicState>({
    resume: null,
    passwordRequired: false,
    loading: true,
    error: null,
  });
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // T146 FR-080 — inject a robots noindex meta tag while this page
  // is mounted. The cleanup removes it on unmount.
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, follow";
    document.head.appendChild(meta);
    return () => {
      meta.remove();
    };
  }, []);

  const fetchResume = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const resume = await getPublicResume(username, slug);
      setState({ resume, passwordRequired: false, loading: false, error: null });
    } catch (err) {
      const code = (err as { code?: string }).code;
      const status = (err as { status?: number }).status;
      if (code === "PASSWORD_REQUIRED" || status === 401) {
        setState({
          resume: null,
          passwordRequired: true,
          loading: false,
          error: null,
        });
        return;
      }
      setState({
        resume: null,
        passwordRequired: false,
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load resume.",
      });
    }
  };

  useEffect(() => {
    if (!username || !slug) return;
    void fetchResume();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, slug]);

  const data = useMemo<ResumeDataV2>(() => {
    if (!state.resume) return defaultResumeDataV2;
    return (state.resume.data as unknown as ResumeDataV2) ?? defaultResumeDataV2;
  }, [state.resume]);

  const TemplateComponent = useMemo(() => {
    const id = data?.metadata?.template ?? "pikachu";
    return templateMap[id as keyof typeof templateMap] ?? templateMap.pikachu;
  }, [data]);

  const handlePasswordSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!password.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await verifyPublicPassword(username, slug, password);
      // Cookie set; refetch the resume.
      await fetchResume();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Incorrect password.");
    } finally {
      setSubmitting(false);
    }
  };

  if (state.loading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-canvas text-sm text-ink-3"
        data-testid="public-loading"
      >
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        正在加载简历…
      </div>
    );
  }

  if (state.passwordRequired) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-canvas p-4"
        data-testid="public-password-form"
      >
        <form
          onSubmit={handlePasswordSubmit}
          className="w-full max-w-sm space-y-2 rounded border border-surface-border bg-surface p-4"
        >
          <div className="flex items-center gap-1.5 text-base font-semibold text-ink-1">
            <Lock className="h-4 w-4" />
            Password Required
          </div>
          <p className="text-xs text-ink-3">
            This resume is password-protected. Enter the password the
            owner shared with you.
          </p>
          <div className="relative">
            <input
              data-testid="public-password-input"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              className="w-full rounded border border-surface-border bg-surface-muted px-2 py-1.5 pr-8 text-sm"
              placeholder="Password"
              disabled={submitting}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-1 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-1"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? (
                <EyeOff className="h-3.5 w-3.5" />
              ) : (
                <Eye className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
          <button
            type="submit"
            data-testid="public-password-submit"
            disabled={submitting || !password.trim()}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : null}
            {submitting ? "Verifying…" : "Unlock"}
          </button>
          {submitError && (
            <p data-testid="public-password-error" className="text-xs text-rose-600">
              {submitError}
            </p>
          )}
        </form>
      </div>
    );
  }

  if (state.error || !state.resume) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-canvas p-4"
        data-testid="public-not-found"
      >
        <div className="max-w-sm space-y-2 text-center">
          <div className="text-base font-semibold text-ink-1">Resume not found</div>
          <p className="text-xs text-ink-3">
            {state.error ?? "This resume is no longer public."}
          </p>
          <Link to="/" className="inline-block text-xs text-primary hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen bg-canvas"
      data-testid="public-resume-root"
    >
      <TemplateComponent data={data} />
    </div>
  );
}
