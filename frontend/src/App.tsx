import { useCallback, useEffect, useRef, useState } from "react";
import { deleteJob, getJob, isMockMode, listJobs, subscribeToMockJob } from "./api";
import { JobCard, JobDetail } from "./components/JobCard";
import { UploadZone } from "./components/UploadZone";
import { isWebSocketEnabled, useJobsWebSocket } from "./hooks/useJobWebSocket";
import type { VideoJob } from "./types";
import "./App.css";

const NON_TERMINAL_STATUSES = new Set(["PENDING", "UPLOADED", "PROCESSING"]);

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
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const deletedJobIdsRef = useRef(new Set<string>());
  const refreshGenerationRef = useRef(0);

  const filterDeleted = useCallback(
    (items: VideoJob[]) => items.filter((job) => !deletedJobIdsRef.current.has(job.jobId)),
    [],
  );

  const nonTerminalJobIds = jobs
    .filter((job) => NON_TERMINAL_STATUSES.has(job.status))
    .map((job) => job.jobId);

  const hasNonTerminalJobs = nonTerminalJobIds.length > 0;

  const applyJobUpdate = useCallback((update: Partial<VideoJob> & { jobId: string }) => {
    if (deletedJobIdsRef.current.has(update.jobId)) return;

    setSelectedJob((current) =>
      current?.jobId === update.jobId ? mergeJob(current, update) : current,
    );
    setJobs((prev) => {
      const existing = prev.find((item) => item.jobId === update.jobId);
      const merged = mergeJob(existing, update);
      const next = existing
        ? prev.map((item) => (item.jobId === update.jobId ? merged : item))
        : [merged, ...prev];
      return dedupeJobs(filterDeleted(next));
    });
  }, [filterDeleted]);

  useJobsWebSocket(nonTerminalJobIds, applyJobUpdate);

  useEffect(() => {
    if (!isMockMode) return;
    const unsubscribers = nonTerminalJobIds.map((jobId) =>
      subscribeToMockJob(jobId, applyJobUpdate),
    );
    return () => {
      for (const unsubscribe of unsubscribers) unsubscribe();
    };
  }, [nonTerminalJobIds.join(","), applyJobUpdate]);

  const refreshJobs = useCallback(async () => {
    const generation = ++refreshGenerationRef.current;
    const data = await listJobs();
    if (generation !== refreshGenerationRef.current) return;

    const fresh = filterDeleted(dedupeJobs(data));
    setJobs(fresh);
    setSelectedJob((current) => {
      if (!current || deletedJobIdsRef.current.has(current.jobId)) return null;
      const updated = fresh.find((j) => j.jobId === current.jobId);
      return updated ?? null;
    });
    setSelectedId((current) => {
      if (!current || deletedJobIdsRef.current.has(current)) return null;
      return fresh.some((j) => j.jobId === current) ? current : null;
    });
  }, [filterDeleted]);

  useEffect(() => {
    refreshJobs().catch(console.error);
  }, [refreshJobs]);

  // Rafraîchissement périodique tant qu'il reste des jobs en cours
  useEffect(() => {
    if (isMockMode || !hasNonTerminalJobs) return;

    const interval = setInterval(() => {
      refreshJobs().catch(console.error);
    }, 4000);

    return () => clearInterval(interval);
  }, [hasNonTerminalJobs, refreshJobs]);

  // Polling rapide par job (complète le WebSocket)
  useEffect(() => {
    if (isMockMode || nonTerminalJobIds.length === 0) return;

    const pollAll = () => {
      for (const jobId of nonTerminalJobIds) {
        getJob(jobId)
          .then(applyJobUpdate)
          .catch(() => undefined);
      }
    };

    pollAll();
    const interval = setInterval(pollAll, 2000);
    return () => clearInterval(interval);
  }, [nonTerminalJobIds.join(","), applyJobUpdate]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshJobs();
    } catch (error) {
      console.error(error);
      window.alert(error instanceof Error ? error.message : "Impossible d'actualiser la liste");
    } finally {
      setRefreshing(false);
    }
  };

  const handleJobStarted = (jobId: string) => {
    setSelectedId(jobId);
  };

  const handleJobCreated = (job: VideoJob) => {
    applyJobUpdate(job);
    setSelectedId(job.jobId);
    setSelectedJob(job);
    refreshJobs().catch(console.error);
  };

  const handleSelect = async (jobId: string) => {
    setSelectedId(jobId);
    try {
      const job = await getJob(jobId);
      applyJobUpdate(job);
      setSelectedJob(job);
    } catch {
      setSelectedJob(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    const job = jobs.find((item) => item.jobId === jobId);
    if (!job || job.status === "PROCESSING") return;

    const confirmed = window.confirm(
      `Supprimer « ${job.filename} » ?\n\nLes fichiers S3 et l'entrée DynamoDB seront supprimés définitivement.`,
    );
    if (!confirmed) return;

    setDeletingId(jobId);
    deletedJobIdsRef.current.add(jobId);
    refreshGenerationRef.current += 1;
    setJobs((prev) => prev.filter((item) => item.jobId !== jobId));
    if (selectedId === jobId) {
      setSelectedId(null);
      setSelectedJob(null);
    }

    try {
      await deleteJob(jobId);
    } catch (error) {
      deletedJobIdsRef.current.delete(jobId);
      console.error(error);
      window.alert(error instanceof Error ? error.message : "Échec de la suppression");
      await refreshJobs();
    } finally {
      setDeletingId(null);
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
              disabled={refreshing}
              onClick={() => handleRefresh()}
            >
              {refreshing ? "Actualisation…" : "Actualiser"}
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
          <JobDetail
            job={selectedJob}
            deleting={selectedJob?.jobId === deletingId}
            onDelete={handleDelete}
          />
        </section>
      </main>

      <footer className="footer">
        <p>VideoFlow — Plateforme serverless complète · AWS Lambda · S3 · DynamoDB · SNS · WebSocket</p>
      </footer>
    </div>
  );
}
