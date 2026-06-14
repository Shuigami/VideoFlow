from utils import (
    api_response,
    generate_presigned_upload_url,
    get_table,
    new_job_id,
    now_iso,
    parse_body,
)

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
}

EXTENSION_TO_CONTENT_TYPE = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mkv": "video/x-matroska",
}


def resolve_content_type(filename: str, content_type: str) -> str | None:
    content_type = (content_type or "").strip()
    if content_type in ALLOWED_CONTENT_TYPES:
        return content_type

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    inferred = EXTENSION_TO_CONTENT_TYPE.get(extension)
    if not inferred:
        return None

    if not content_type or content_type == "application/octet-stream":
        return inferred

    return inferred


def lambda_handler(event, context):
    try:
        body = parse_body(event)
        filename = body.get("filename", "").strip()
        content_type = body.get("contentType", "video/mp4").strip()

        if not filename:
            return api_response(400, {"error": "filename is required"})

        resolved_type = resolve_content_type(filename, content_type)
        if not resolved_type:
            return api_response(
                400,
                {
                    "error": "Unsupported content type",
                    "allowed": sorted(ALLOWED_CONTENT_TYPES),
                },
            )

        job_id = new_job_id()
        presigned = generate_presigned_upload_url(job_id, filename, resolved_type)
        timestamp = now_iso()

        job = {
            "jobId": job_id,
            "filename": filename,
            "contentType": resolved_type,
            "status": "PENDING",
            "s3Key": presigned["s3Key"],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        get_table().put_item(Item=job)

        return api_response(
            201,
            {
                "jobId": job_id,
                "uploadUrl": presigned["uploadUrl"],
                "status": "PENDING",
                "expiresIn": 3600,
            },
        )

    except Exception as exc:
        return api_response(500, {"error": str(exc)})
