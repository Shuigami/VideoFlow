export const VIDEO_CONTENT_TYPES = [
  "video/mp4",
  "video/webm",
  "video/quicktime",
  "video/x-msvideo",
  "video/x-matroska",
] as const;

export type VideoContentType = (typeof VIDEO_CONTENT_TYPES)[number];

const EXTENSION_TO_CONTENT_TYPE: Record<string, VideoContentType> = {
  mp4: "video/mp4",
  webm: "video/webm",
  mov: "video/quicktime",
  avi: "video/x-msvideo",
  mkv: "video/x-matroska",
};

export function getFileExtension(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? parts.pop()!.toLowerCase() : "";
}

/** Brave et certains navigateurs laissent file.type vide ou renvoient application/octet-stream. */
export function resolveVideoContentType(file: File): VideoContentType | null {
  if (VIDEO_CONTENT_TYPES.includes(file.type as VideoContentType)) {
    return file.type as VideoContentType;
  }

  const fromExtension = EXTENSION_TO_CONTENT_TYPE[getFileExtension(file.name)];
  if (!fromExtension) return null;

  if (!file.type || file.type === "application/octet-stream") {
    return fromExtension;
  }

  return fromExtension;
}

export const VIDEO_FILE_ACCEPT = [
  ...VIDEO_CONTENT_TYPES,
  ...Object.keys(EXTENSION_TO_CONTENT_TYPE).map((ext) => `.${ext}`),
].join(",");
