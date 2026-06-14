import { useEffect, useRef } from "react";
import type { VideoJob } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "";

export function useJobsWebSocket(
  jobIds: string[],
  onUpdate: (update: Partial<VideoJob> & { jobId: string }) => void,
) {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const jobIdsKey = jobIds.join(",");

  useEffect(() => {
    if (!WS_URL || !jobIdsKey) return;

    const ids = jobIdsKey.split(",");
    const sockets = ids.map((jobId) => {
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

      return socket;
    });

    return () => {
      for (const socket of sockets) {
        socket.close();
      }
    };
  }, [jobIdsKey]);
}

/** @deprecated Use useJobsWebSocket — kept for single-job use */
export function useJobWebSocket(
  jobId: string | null,
  onUpdate: (update: Partial<VideoJob> & { jobId: string }) => void,
) {
  useJobsWebSocket(jobId ? [jobId] : [], onUpdate);
}

export const isWebSocketEnabled = Boolean(import.meta.env.VITE_WS_URL);
