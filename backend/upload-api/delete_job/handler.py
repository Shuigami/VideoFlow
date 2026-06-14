from utils import api_response, delete_job_assets, get_table


def lambda_handler(event, context):
    try:
        job_id = event.get("pathParameters", {}).get("jobId")
        if not job_id:
            return api_response(400, {"error": "jobId is required"})

        response = get_table().get_item(Key={"jobId": job_id})
        job = response.get("Item")

        if not job:
            return api_response(404, {"error": "Job not found"})

        if job.get("status") == "PROCESSING":
            return api_response(
                409,
                {"error": "Impossible de supprimer un job en cours de traitement"},
            )

        # DynamoDB d'abord : la liste ne doit plus afficher le job même si le nettoyage S3 échoue
        get_table().delete_item(Key={"jobId": job_id})

        try:
            delete_job_assets(job)
        except Exception as exc:
            print(f"S3 cleanup failed for job {job_id}: {exc}")

        return api_response(200, {"message": "Job supprimé", "jobId": job_id})

    except Exception as exc:
        return api_response(500, {"error": str(exc)})
