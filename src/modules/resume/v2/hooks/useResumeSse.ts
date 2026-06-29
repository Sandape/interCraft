// T118 — useResumeSse hook (US12 cross-tab sync).
//
// Subscribes to the SSE stream at GET /api/v1/v2/resumes/events so
// other tabs / clients editing the same resume can broadcast their
// PUTs without re-fetching. The store applies incoming `data` blobs
// via `resetFromServer` so undo/redo and isDirty are preserved.
//
// Event shape (from backend/app/api/v1/ws/resume_v2.py):
//   id: integer
//   event: connected | resume.updated | resume.public-changed | message | stream.unavailable
//   data: { type, resume_id?, user_id?, data? ... }
//
// Auto-reconnect: on `error` we wait 3s and open a new EventSource.
// Cleanup on unmount closes the source.
//
// Fail-open: if the WS endpoint is not reachable (no backend, network
// down), the hook silently no-ops — the editor still works via direct
// REST PUT, just without cross-tab sync.

import { useEffect, useRef } from "react";
import { env } from "@/api/env";
import { getAccessToken } from "@/api/token-storage";
import { useResumeV2Store } from "../store";
import type { ResumeDataV2 } from "../schema/data";

interface SseEventPayload {
  type?: string;
  resume_id?: string;
  user_id?: string;
  data?: ResumeDataV2;
  version?: number;
  message?: string;
}

const RECONNECT_DELAY_MS = 3000;

export function useResumeSse(
  resumeId: string | null | undefined,
  onUpdate?: (data: ResumeDataV2) => void,
): void {
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    if (!resumeId) return;
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }

    let cancelled = false;
    let es: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const open = () => {
      if (cancelled) return;
      // Pass the auth token via query param because EventSource
      // cannot set custom headers. The backend endpoint is open to
      // any user_id from the JWT — the query param is the convention
      // T118 established.
      const access = getAccessToken();
      const params = new URLSearchParams({ resume_id: resumeId });
      if (access) params.set("token", access);
      const base = env.API_BASE_URL || window.location.origin;
      const url = `${base}/api/v1/v2/resumes/events?${params.toString()}`;

      try {
        es = new EventSource(url, { withCredentials: false });
      } catch {
        // EventSource constructor can throw on bad URLs. Fail-open.
        scheduleReconnect();
        return;
      }

      es.addEventListener("connected", () => {
        // No-op: stream is up. We could update a status indicator
        // here in a future iteration.
      });

      es.addEventListener("resume.updated", (evt) => {
        const ev = evt as MessageEvent<string>;
        let payload: SseEventPayload = {};
        try {
          payload = JSON.parse(ev.data) as SseEventPayload;
        } catch {
          return;
        }
        if (!payload.data) return;
        // Filter to the resume the editor is currently viewing. The
        // backend already filters by `resume_id` from the query, but
        // we double-check defensively in case the channel is shared.
        if (payload.resume_id && payload.resume_id !== resumeId) return;
        // Hand off to the consumer (or push into the store by default).
        if (onUpdateRef.current) {
          onUpdateRef.current(payload.data);
        } else {
          const store = useResumeV2Store.getState();
          store.resetFromServer({
            id: resumeId,
            data: payload.data,
            version: payload.version ?? store.version,
          });
        }
      });

      es.addEventListener("resume.public-changed", () => {
        // Public-state changes don't mutate the `data` blob; the
        // editor will refetch via the list/page nav. Future US may
        // surface this through the share button's badge.
      });

      es.addEventListener("error", () => {
        // EventSource auto-retries, but if the connection has been
        // closed (readyState === CLOSED) we own the reconnect. Fail-open.
        if (es && es.readyState === EventSource.CLOSED) {
          scheduleReconnect();
        }
      });
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      if (reconnectTimer) return;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        open();
      }, RECONNECT_DELAY_MS);
    };

    open();

    return () => {
      cancelled = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (es) {
        es.close();
        es = null;
      }
    };
  }, [resumeId]);
}