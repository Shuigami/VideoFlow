import { useEffect, useRef } from "react";
import type { VideoJob } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "";

export function useJobWebSocket(
  jobId: string | null,
  onUpdate: (update: Partial<VideoJob> & { jobId: string }) => void,
) {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    if (!jobId || !WS_URL) return;

    const socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      socket.send(JSON.stringify({ action: "subscribe", jobId }));
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "job_update" && payload.job) {
          onUpdateRef.current(payload.job as VideoJob);
        }
      } catch {
        /* ignore malformed messages */
      }
    };

    return () => socket.close();
  }, [jobId]);
}

export const isWebSocketEnabled = Boolean(import.meta.env.VITE_WS_URL);
