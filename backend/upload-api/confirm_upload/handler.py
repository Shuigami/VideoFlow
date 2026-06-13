from utils import api_response, emit_video_uploaded_event, get_table, now_iso


def lambda_handler(event, context):
    try:
        job_id = event.get("pathParameters", {}).get("jobId")
        if not job_id:
            return api_response(400, {"error": "jobId is required"})

        table = get_table()
        response = table.get_item(Key={"jobId": job_id})
        job = response.get("Item")

        if not job:
            return api_response(404, {"error": "Job not found"})

        if job["status"] not in ("PENDING", "UPLOADED"):
            return api_response(200, job)

        timestamp = now_iso()
        updated = {
            **job,
            "status": "UPLOADED",
            "updatedAt": timestamp,
            "uploadedAt": timestamp,
        }

        table.put_item(Item=updated)
        emit_video_uploaded_event(updated)

        return api_response(
            200,
            {
                **updated,
                "message": "Upload confirmed. Processing pipeline will start shortly.",
            },
        )

    except Exception as exc:
        return api_response(500, {"error": str(exc)})
