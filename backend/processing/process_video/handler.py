import json
import os
import tempfile
from pathlib import Path

from utils import (
    enrich_job_with_urls,
    notify_job_subscribers,
    now_iso,
    publish_sns_notification,
    s3_client,
    update_job,
)
from video_processor import process_video

UPLOAD_BUCKET = os.environ["UPLOAD_BUCKET"]
PROCESSED_BUCKET = os.environ["PROCESSED_BUCKET"]


def upload_file(local_path: Path, key: str, content_type: str) -> None:
    s3_client.upload_file(
        str(local_path),
        PROCESSED_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def download_source(bucket: str, key: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, key, str(destination))


def lambda_handler(event, context):
    detail = event.get("detail") or {}
    if isinstance(detail, str):
        detail = json.loads(detail)

    job_id = detail["jobId"]
    source_bucket = detail.get("bucket", UPLOAD_BUCKET)
    source_key = detail["key"]

    try:
        processing_job = update_job(job_id, {"status": "PROCESSING", "processingStartedAt": now_iso()})
        notify_job_subscribers(job_id, enrich_job_with_urls(processing_job))

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            source_path = work_dir / "source"
            download_source(source_bucket, source_key, source_path)

            result = process_video(source_path, work_dir / "outputs")

            output_keys: dict[str, str] = {}
            for quality, local_file in result["outputs"].items():
                key = f"processed/{job_id}/{quality}.mp4"
                upload_file(local_file, key, "video/mp4")
                output_keys[quality] = key

            thumbnail_key = f"processed/{job_id}/thumbnail.jpg"
            upload_file(result["thumbnail"], thumbnail_key, "image/jpeg")

            completed_job = update_job(
                job_id,
                {
                    "status": "COMPLETED",
                    "completedAt": now_iso(),
                    "metadata": result["metadata"],
                    "outputs": output_keys,
                    "thumbnailKey": thumbnail_key,
                },
            )

            enriched = enrich_job_with_urls(completed_job)
            publish_sns_notification(enriched)
            notify_job_subscribers(job_id, enriched)

            return {"statusCode": 200, "body": json.dumps({"jobId": job_id, "status": "COMPLETED"})}

    except Exception as exc:
        failed_job = update_job(
            job_id,
            {
                "status": "FAILED",
                "error": str(exc),
                "failedAt": now_iso(),
            },
        )
        notify_job_subscribers(job_id, enrich_job_with_urls(failed_job))
        raise
