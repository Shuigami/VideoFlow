import { useCallback, useEffect, useState } from "react";
import { getJob, isMockMode, listJobs, subscribeToMockJob } from "./api";
import { JobCard, JobDetail } from "./components/JobCard";
import { UploadZone } from "./components/UploadZone";
import { isWebSocketEnabled, useJobWebSocket } from "./hooks/useJobWebSocket";
import type { VideoJob } from "./types";
import "./App.css";

const ACTIVE_STATUSES = new Set(["UPLOADED", "PROCESSING"]);

function dedupeJobs(jobs: VideoJob[]): VideoJob[] {
  const byId = new Map<string, VideoJob>();
  for (const job of jobs) {
    byId.set(job.jobId, job);
  }
  return Array.from(byId.values()).sort((a, b) =>
    (b.createdAt ?? "").localeCompare(a.createdAt ?? ""),
  );
}

function mergeJob(existing: VideoJob | undefined, update: Partial<VideoJob> & { jobId: string }): VideoJob {
  if (!existing) return update as VideoJob;
  return { ...existing, ...update };
}

export default function App() {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<VideoJob | null>(null);

  const applyJobUpdate = useCallback((update: Partial<VideoJob> & { jobId: string }) => {
    setSelectedJob((current) =>
      current?.jobId === update.jobId ? mergeJob(current, update) : current,
    );
    setJobs((prev) => {
      const existing = prev.find((item) => item.jobId === update.jobId);
      const merged = mergeJob(existing, update);
      const next = existing
        ? prev.map((item) => (item.jobId === update.jobId ? merged : item))
        : [merged, ...prev];
      return dedupeJobs(next);
    });
  }, []);

  useJobWebSocket(selectedId, applyJobUpdate);

  useEffect(() => {
    if (!selectedId || !isMockMode) return;
    return subscribeToMockJob(selectedId, applyJobUpdate);
  }, [selectedId, applyJobUpdate]);

  const refreshJobs = useCallback(async () => {
    const data = await listJobs();
    const enriched = await Promise.all(
      data.map(async (job) => {
        if (job.thumbnailUrl || job.status === "PENDING") return job;
        try {
          return await getJob(job.jobId);
        } catch {
          return job;
        }
      }),
    );
    const fresh = dedupeJobs(enriched);
    setJobs(fresh);
    setSelectedJob((current) => {
      if (!current) return current;
      const updated = fresh.find((j) => j.jobId === current.jobId);
      return updated ? mergeJob(current, updated) : current;
    });
  }, []);

  useEffect(() => {
    refreshJobs().catch(console.error);
  }, [refreshJobs]);

  // Polling de secours pour tous les jobs actifs (pas seulement le job sélectionné)
  const activeJobIds = jobs
    .filter((job) => ACTIVE_STATUSES.has(job.status))
    .map((job) => job.jobId)
    .join(",");

  useEffect(() => {
    if (isMockMode || !activeJobIds) return;

    const pollAll = () => {
      for (const jobId of activeJobIds.split(",")) {
        getJob(jobId)
          .then(applyJobUpdate)
          .catch(() => undefined);
      }
    };

    pollAll();
    const interval = setInterval(pollAll, 1500);
    return () => clearInterval(interval);
  }, [activeJobIds, applyJobUpdate]);

  const handleJobStarted = (jobId: string) => {
    setSelectedId(jobId);
  };

  const handleJobCreated = (job: VideoJob) => {
    applyJobUpdate(job);
    setSelectedId(job.jobId);
    setSelectedJob(job);
  };

  const handleSelect = async (jobId: string) => {
    setSelectedId(jobId);
    try {
      const job = await getJob(jobId);
      setSelectedJob(job);
    } catch {
      setSelectedJob(null);
    }
  };

  const modeLabel = isMockMode
    ? "Mode démo mock"
    : isWebSocketEnabled
      ? "Temps réel WebSocket + polling"
      : "API REST";

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-content">
          <div className="hero-badge">Serverless · Event-Driven · FFmpeg · {modeLabel}</div>
          <h1>VideoFlow</h1>
          <p className="hero-subtitle">
            Plateforme complète de traitement vidéo — upload S3, pipeline FFmpeg
            (144p → 1080p), analyse automatique et notifications temps réel.
          </p>
          {isMockMode && (
            <div className="mock-banner">
              Mode mock actif. Pour FFmpeg réel : lancez le serveur local sur le port 8000.
            </div>
          )}
        </div>

        <div className="architecture-mini">
          <div className="arch-step">Frontend</div>
          <div className="arch-arrow">→</div>
          <div className="arch-step">API Gateway</div>
          <div className="arch-arrow">→</div>
          <div className="arch-step">S3</div>
          <div className="arch-arrow">→</div>
          <div className="arch-step highlight">EventBridge</div>
          <div className="arch-arrow">→</div>
          <div className="arch-step">FFmpeg</div>
          <div className="arch-arrow">→</div>
          <div className="arch-step highlight">WebSocket</div>
        </div>
      </header>

      <main className="main-grid">
        <section className="panel upload-panel">
          <h2>Nouvel upload</h2>
          <UploadZone onJobCreated={handleJobCreated} onJobStarted={handleJobStarted} />
        </section>

        <section className="panel jobs-panel">
          <div className="panel-header">
            <h2>Jobs récents</h2>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => refreshJobs().catch(console.error)}
            >
              Actualiser
            </button>
          </div>
          <div className="jobs-list">
            {jobs.length === 0 ? (
              <p className="empty-list">Aucun job — uploadez une vidéo pour commencer.</p>
            ) : (
              jobs.map((job) => (
                <JobCard
                  key={job.jobId}
                  job={job}
                  selected={job.jobId === selectedId}
                  onSelect={handleSelect}
                />
              ))
            )}
          </div>
        </section>

        <section className="panel detail-panel">
          <h2>Détail du pipeline</h2>
          <JobDetail job={selectedJob} />
        </section>
      </main>

      <footer className="footer">
        <p>VideoFlow — Plateforme serverless complète · AWS Lambda · S3 · DynamoDB · SNS · WebSocket</p>
      </footer>
    </div>
  );
}
