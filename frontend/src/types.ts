export type JobStatus =
  | "PENDING"
  | "UPLOADED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

export interface VideoMetadata {
  duration?: number;
  width?: number;
  height?: number;
  codec?: string;
  sizeBytes?: number;
}

export interface VideoJob {
  jobId: string;
  filename: string;
  contentType: string;
  status: JobStatus;
  s3Key?: string;
  createdAt: string;
  updatedAt: string;
  uploadedAt?: string;
  completedAt?: string;
  processingStartedAt?: string;
  failedAt?: string;
  metadata?: VideoMetadata;
  outputs?: Record<string, string>;
  outputUrls?: Record<string, string>;
  thumbnailUrl?: string;
  thumbnailKey?: string;
  message?: string;
  error?: string;
}

export interface CreateJobResponse {
  jobId: string;
  uploadUrl: string;
  status: JobStatus;
  expiresIn: number;
}
