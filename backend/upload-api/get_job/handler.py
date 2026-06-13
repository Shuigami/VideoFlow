from utils import api_response, enrich_job_with_urls, get_table


def lambda_handler(event, context):
    try:
        job_id = event.get("pathParameters", {}).get("jobId")
        if not job_id:
            return api_response(400, {"error": "jobId is required"})

        response = get_table().get_item(Key={"jobId": job_id})
        job = response.get("Item")

        if not job:
            return api_response(404, {"error": "Job not found"})

        return api_response(200, enrich_job_with_urls(job))

    except Exception as exc:
        return api_response(500, {"error": str(exc)})
