import type { CreateJobResponse, VideoJob } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const MOCK_MODE = import.meta.env.VITE_MOCK_API === "true";

const mockJobs = new Map<string, VideoJob>();
const mockListeners = new Map<string, Set<(job: VideoJob) => void>>();

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function notifyMock(jobId: string, job: VideoJob) {
  mockJobs.set(jobId, job);
  mockListeners.get(jobId)?.forEach((listener) => listener(job));
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error ?? error.detail ?? `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function mockCreateJob(
  filename: string,
  contentType: string,
): Promise<CreateJobResponse> {
  await delay(400);
  const jobId = crypto.randomUUID();
  const now = new Date().toISOString();

  mockJobs.set(jobId, {
    jobId,
    filename,
    contentType,
    status: "PENDING",
    createdAt: now,
    updatedAt: now,
  });

  return {
    jobId,
    uploadUrl: "mock://upload",
    status: "PENDING",
    expiresIn: 3600,
  };
}

async function mockConfirmUpload(jobId: string): Promise<VideoJob> {
  await delay(300);
  const job = mockJobs.get(jobId);
  if (!job) throw new Error("Job not found");

  const updated: VideoJob = {
    ...job,
    status: "UPLOADED",
    updatedAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    message: "Upload confirmé — pipeline FFmpeg simulé.",
  };
  notifyMock(jobId, updated);

  setTimeout(() => {
    notifyMock(jobId, { ...updated, status: "PROCESSING", updatedAt: new Date().toISOString() });
  }, 1500);

  setTimeout(() => {
    notifyMock(jobId, {
      ...updated,
      status: "COMPLETED",
      completedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      metadata: { duration: 142, width: 1920, height: 1080, codec: "h264", sizeBytes: 48_000_000 },
      outputs: { "144p": "144p.mp4", "360p": "360p.mp4", "480p": "480p.mp4", "720p": "720p.mp4", "1080p": "1080p.mp4" },
      outputUrls: { "144p": "#", "360p": "#", "480p": "#", "720p": "#", "1080p": "#" },
      thumbnailUrl:
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'%3E%3Crect fill='%231a2234' width='320' height='180'/%3E%3Cpolygon fill='%236366f1' points='130,70 130,110 170,90'/%3E%3C/svg%3E",
      message: "Traitement terminé — 144p à 1080p disponibles.",
    });
  }, 4500);

  return updated;
}

export async function createJob(
  filename: string,
  contentType: string,
): Promise<CreateJobResponse> {
  if (MOCK_MODE) return mockCreateJob(filename, contentType);
  return request<CreateJobResponse>("/jobs", {
    method: "POST",
    body: JSON.stringify({ filename, contentType }),
  });
}

export async function confirmUpload(jobId: string): Promise<VideoJob> {
  if (MOCK_MODE) return mockConfirmUpload(jobId);
  return request<VideoJob>(`/jobs/${jobId}/confirm`, { method: "POST" });
}

export async function getJob(jobId: string): Promise<VideoJob> {
  if (MOCK_MODE) {
    await delay(200);
    const job = mockJobs.get(jobId);
    if (!job) throw new Error("Job not found");
    return job;
  }
  return request<VideoJob>(`/jobs/${jobId}`);
}

export async function listJobs(): Promise<VideoJob[]> {
  if (MOCK_MODE) {
    await delay(200);
    return Array.from(mockJobs.values()).sort((a, b) =>
      b.createdAt.localeCompare(a.createdAt),
    );
  }
  const data = await request<{ jobs: VideoJob[] }>("/jobs?limit=20");
  return data.jobs;
}

export async function uploadToS3(
  uploadUrl: string,
  file: File,
  onProgress: (percent: number) => void,
  contentType?: string,
): Promise<void> {
  if (MOCK_MODE) {
    for (let i = 0; i <= 100; i += 10) {
      await delay(80);
      onProgress(i);
    }
    return;
  }

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else {
        const detail = xhr.responseText?.slice(0, 200);
        reject(new Error(`Upload S3 échoué (HTTP ${xhr.status})${detail ? `: ${detail}` : ""}`));
      }
    });
    xhr.addEventListener("error", () =>
      reject(new Error("Upload S3 bloqué (CORS ou réseau). Redéployez l'API si le problème persiste.")),
    );
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", contentType ?? file.type);
    xhr.send(file);
  });
}

export function subscribeToMockJob(jobId: string, listener: (job: VideoJob) => void): () => void {
  if (!MOCK_MODE) return () => {};
  const listeners = mockListeners.get(jobId) ?? new Set();
  listeners.add(listener);
  mockListeners.set(jobId, listeners);
  const current = mockJobs.get(jobId);
  if (current) listener(current);
  return () => {
    listeners.delete(listener);
  };
}

export const isMockMode = MOCK_MODE;
