from utils import get_connections_table, parse_body, ws_response


def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    body = parse_body(event)
    job_id = body.get("jobId")

    if not job_id:
        return ws_response(400, {"error": "jobId is required"})

    get_connections_table().update_item(
        Key={"connectionId": connection_id},
        UpdateExpression="SET jobId = :jobId",
        ExpressionAttributeValues={":jobId": job_id},
    )

    return ws_response(200, {"message": "subscribed", "jobId": job_id})
