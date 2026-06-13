import type { JobStatus } from "../types";

const STATUS_CONFIG: Record<
  JobStatus,
  { label: string; color: string; step: number }
> = {
  PENDING: { label: "En attente", color: "#94a3b8", step: 0 },
  UPLOADED: { label: "Uploadé", color: "#38bdf8", step: 1 },
  PROCESSING: { label: "Traitement", color: "#fbbf24", step: 2 },
  COMPLETED: { label: "Terminé", color: "#34d399", step: 3 },
  FAILED: { label: "Échec", color: "#f87171", step: -1 },
};

const PIPELINE_STEPS = ["Upload", "Événement", "Transcodage", "Terminé"];

interface StatusBadgeProps {
  status: JobStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status ?? "Inconnu",
    color: "#94a3b8",
    step: 0,
  };
  const style = { "--badge-color": config.color } as Record<string, string>;

  return (
    <span className="status-badge" style={style}>
      <span className="status-dot" />
      {config.label}
    </span>
  );
}

interface PipelineProgressProps {
  status: JobStatus;
}

export function PipelineProgress({ status }: PipelineProgressProps) {
  const currentStep = STATUS_CONFIG[status]?.step ?? 0;

  return (
    <div className="pipeline">
      {PIPELINE_STEPS.map((step, index) => {
        const isActive = index <= currentStep && currentStep >= 0;
        const isCurrent = index === currentStep;
        return (
          <div
            key={step}
            className={`pipeline-step ${isActive ? "active" : ""} ${isCurrent ? "current" : ""}`}
          >
            <div className="pipeline-node">{index + 1}</div>
            <span className="pipeline-label">{step}</span>
            {index < PIPELINE_STEPS.length - 1 && (
              <div className={`pipeline-line ${index < currentStep ? "filled" : ""}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
