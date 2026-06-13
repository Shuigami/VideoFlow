import { PipelineProgress, StatusBadge } from "./StatusBadge";
import type { VideoJob } from "../types";

interface JobCardProps {
  job: VideoJob;
  selected?: boolean;
  onSelect: (jobId: string) => void;
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function sortQualities(qualities: string[]) {
  return [...qualities].sort(
    (a, b) => parseInt(a, 10) - parseInt(b, 10),
  );
}

function formatDuration(seconds?: number) {
  if (!seconds) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function JobCard({ job, selected, onSelect }: JobCardProps) {
  return (
    <article
      className={`job-card ${selected ? "selected" : ""}`}
      onClick={() => onSelect(job.jobId)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect(job.jobId)}
    >
      <div className="job-card-header">
        {job.thumbnailUrl ? (
          <img src={job.thumbnailUrl} alt="" className="job-thumb" />
        ) : (
          <div className="job-thumb placeholder" />
        )}
        <div className="job-card-body">
          <span className="job-filename truncate-text" title={job.filename}>
            {job.filename}
          </span>
          <div className="job-card-meta">
            <span>{formatDate(job.createdAt)}</span>
            <span className="job-id">{job.jobId.slice(0, 8)}…</span>
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>
    </article>
  );
}

interface JobDetailProps {
  job: VideoJob | null;
}

export function JobDetail({ job }: JobDetailProps) {
  if (!job) {
    return (
      <div className="job-detail empty">
        <p>Sélectionnez un job pour voir le détail du pipeline serverless.</p>
      </div>
    );
  }

  return (
    <div className="job-detail">
      <header>
        <h2 className="truncate-text" title={job.filename}>
          {job.filename}
        </h2>
        <StatusBadge status={job.status} />
      </header>

      {job.thumbnailUrl && (
        <div className="thumbnail-preview">
          <img src={job.thumbnailUrl} alt={`Miniature de ${job.filename}`} />
        </div>
      )}

      <PipelineProgress status={job.status} />

      <dl className="detail-grid">
        <div>
          <dt>Job ID</dt>
          <dd className="mono">{job.jobId}</dd>
        </div>
        <div>
          <dt>Statut</dt>
          <dd>{job.status}</dd>
        </div>
        <div>
          <dt>Créé le</dt>
          <dd>{formatDate(job.createdAt)}</dd>
        </div>
        {job.uploadedAt && (
          <div>
            <dt>Uploadé le</dt>
            <dd>{formatDate(job.uploadedAt)}</dd>
          </div>
        )}
        {job.completedAt && (
          <div>
            <dt>Terminé le</dt>
            <dd>{formatDate(job.completedAt)}</dd>
          </div>
        )}
        {job.s3Key && (
          <div className="full-width">
            <dt>Clé S3</dt>
            <dd className="mono">{job.s3Key}</dd>
          </div>
        )}
        {job.metadata && (
          <>
            <div>
              <dt>Durée</dt>
              <dd>{formatDuration(job.metadata.duration)}</dd>
            </div>
            <div>
              <dt>Résolution source</dt>
              <dd>
                {job.metadata.width}×{job.metadata.height}
              </dd>
            </div>
            <div>
              <dt>Codec</dt>
              <dd>{job.metadata.codec}</dd>
            </div>
            {job.metadata.sizeBytes && (
              <div>
                <dt>Taille</dt>
                <dd>{(job.metadata.sizeBytes / 1_048_576).toFixed(1)} Mo</dd>
              </div>
            )}
          </>
        )}
      </dl>

      {job.outputUrls && Object.keys(job.outputUrls).length > 0 && (
        <div className="outputs-section">
          <h3>Vidéos transcodées</h3>
          <div className="output-links">
            {sortQualities(Object.keys(job.outputUrls)).map((quality) => (
              <a
                key={quality}
                href={job.outputUrls![quality]}
                className="output-link"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="output-quality">{quality}</span>
                <span className="output-action">Télécharger / Lire</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {job.message && <p className="job-message">{job.message}</p>}

      {job.error && (
        <div className="error-banner">
          <strong>Erreur :</strong> {job.error}
        </div>
      )}

      {job.status === "PROCESSING" && (
        <div className="info-banner processing">
          Pipeline FFmpeg en cours — transcodage 144p → 1080p et génération de miniature…
        </div>
      )}

      {job.status === "COMPLETED" && (
        <div className="info-banner success">
          Notification SNS envoyée · Mise à jour WebSocket diffusée aux clients abonnés.
        </div>
      )}
    </div>
  );
}
