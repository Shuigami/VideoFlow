import { useCallback, useRef, useState } from "react";
import { confirmUpload, createJob, uploadToS3 } from "../api";
import type { VideoJob } from "../types";

interface UploadZoneProps {
  onJobCreated: (job: VideoJob) => void;
  onJobStarted?: (jobId: string) => void;
}

const ACCEPTED_TYPES = [
  "video/mp4",
  "video/webm",
  "video/quicktime",
  "video/x-msvideo",
  "video/x-matroska",
];

export function UploadZone({ onJobCreated, onJobStarted }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [currentFile, setCurrentFile] = useState<string | null>(null);

  const processFile = useCallback(
    async (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError("Format non supporté. Utilisez MP4, WebM, MOV, AVI ou MKV.");
        return;
      }

      setError(null);
      setUploading(true);
      setProgress(0);
      setCurrentFile(file.name);

      try {
        const { jobId, uploadUrl } = await createJob(file.name, file.type);
        onJobStarted?.(jobId);
        await uploadToS3(uploadUrl, file, setProgress, file.type);
        const job = await confirmUpload(jobId);
        onJobCreated(job);
        setCurrentFile(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setUploading(false);
        setProgress(0);
      }
    },
    [onJobCreated, onJobStarted],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setDragging(false);
      const file = event.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile],
  );

  return (
    <section className="upload-zone">
      <div
        className={`drop-area ${dragging ? "dragging" : ""} ${uploading ? "uploading" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) processFile(file);
            e.target.value = "";
          }}
        />

        {uploading ? (
          <div className="upload-progress">
            <div className="progress-ring">
              <svg viewBox="0 0 36 36">
                <path
                  className="progress-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="progress-fill"
                  strokeDasharray={`${progress}, 100`}
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="progress-text">{progress}%</span>
            </div>
            <p className="upload-filename truncate-text" title={currentFile ?? undefined}>
              {currentFile}
            </p>
            <p className="upload-hint">Upload direct vers S3 via URL présignée</p>
          </div>
        ) : (
          <>
            <div className="drop-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 16V4m0 0l-4 4m4-4l4 4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
              </svg>
            </div>
            <p className="drop-title">Glissez une vidéo ici</p>
            <p className="drop-subtitle">ou cliquez pour parcourir — MP4, WebM, MOV jusqu'à 500 Mo</p>
          </>
        )}
      </div>

      {error && <p className="error-message">{error}</p>}
    </section>
  );
}
