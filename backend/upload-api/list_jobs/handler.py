from utils import api_response, enrich_job_with_urls, get_table


def lambda_handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", "20"))
        limit = min(max(limit, 1), 100)

        response = get_table().scan(Limit=limit)
        jobs = sorted(
            response.get("Items", []),
            key=lambda j: j.get("createdAt", ""),
            reverse=True,
        )

        enriched_jobs = [enrich_job_with_urls(job) for job in jobs]

        return api_response(200, {"jobs": enriched_jobs, "count": len(enriched_jobs)})

    except Exception as exc:
        return api_response(500, {"error": str(exc)})
