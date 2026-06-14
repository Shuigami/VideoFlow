"""Utilitaires partagés entre les Lambdas VideoFlow."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

JOBS_TABLE = os.environ.get("JOBS_TABLE", "")
UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "")
PROCESSED_BUCKET = os.environ.get("PROCESSED_BUCKET", "")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "")
CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "")
WEBSOCKET_ENDPOINT = os.environ.get("WEBSOCKET_ENDPOINT", "")
NOTIFICATIONS_TOPIC_ARN = os.environ.get("NOTIFICATIONS_TOPIC_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ca-central-1"))

dynamodb = boto3.resource("dynamodb")
_s3_config = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
# Endpoint régional obligatoire : sinon le navigateur reçoit une 307 sans CORS → upload bloqué
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
    config=_s3_config,
)
events_client = boto3.client("events")
sns_client = boto3.client("sns")

_apigw_management = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_job_id() -> str:
    return str(uuid4())


def get_table():
    return dynamodb.Table(JOBS_TABLE)


def get_connections_table():
    return dynamodb.Table(CONNECTIONS_TABLE)


def get_apigw_management():
    global _apigw_management
    if _apigw_management is None and WEBSOCKET_ENDPOINT:
        _apigw_management = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=WEBSOCKET_ENDPOINT,
        )
    return _apigw_management


def decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def to_dynamo(value: Any) -> Any:
    """Convertit les float en Decimal pour DynamoDB (types imbriqués inclus)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def api_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=decimal_default),
    }


def ws_response(status_code: int, body: dict | None = None) -> dict:
    payload: dict[str, Any] = {"statusCode": status_code}
    if body is not None:
        payload["body"] = json.dumps(body)
    return payload


def parse_body(event: dict) -> dict:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body) if isinstance(body, str) else body


def generate_presigned_upload_url(job_id: str, filename: str, content_type: str) -> dict:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"
    key = f"uploads/{job_id}/source.{extension}"

    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": UPLOAD_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )

    return {"uploadUrl": upload_url, "s3Key": key}


def generate_presigned_download_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def enrich_job_with_urls(job: dict) -> dict:
    enriched = dict(job)
    if PROCESSED_BUCKET and job.get("outputs"):
        enriched["outputUrls"] = {
            quality: generate_presigned_download_url(PROCESSED_BUCKET, key)
            for quality, key in job["outputs"].items()
        }
    if PROCESSED_BUCKET and job.get("thumbnailKey"):
        enriched["thumbnailUrl"] = generate_presigned_download_url(
            PROCESSED_BUCKET, job["thumbnailKey"]
        )
    return enriched


def update_job(job_id: str, updates: dict) -> dict:
    table = get_table()
    expression_parts = []
    expression_values: dict[str, Any] = {}
    expression_names: dict[str, str] = {}

    updates = {**updates, "updatedAt": now_iso()}
    updates = {key: to_dynamo(value) for key, value in updates.items()}

    for index, (key, value) in enumerate(updates.items()):
        placeholder = f":v{index}"
        name_key = f"#k{index}"
        expression_parts.append(f"{name_key} = {placeholder}")
        expression_values[placeholder] = value
        expression_names[name_key] = key

    response = table.update_item(
        Key={"jobId": job_id},
        UpdateExpression="SET " + ", ".join(expression_parts),
        ExpressionAttributeValues=expression_values,
        ExpressionAttributeNames=expression_names,
        ReturnValues="ALL_NEW",
    )
    return response["Attributes"]


def emit_video_uploaded_event(job: dict) -> None:
    if not EVENT_BUS_NAME:
        return

    events_client.put_events(
        Entries=[
            {
                "Source": "videoflow.upload",
                "DetailType": "Video Uploaded",
                "Detail": json.dumps(
                    {
                        "jobId": job["jobId"],
                        "bucket": UPLOAD_BUCKET,
                        "key": job["s3Key"],
                        "filename": job["filename"],
                        "contentType": job.get("contentType", "video/mp4"),
                    }
                ),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )


def sanitize_sns_subject(text: str, max_length: int = 100) -> str:
    """SNS Subject must be ASCII and at most 100 characters (email subscriptions)."""
    ascii_text = text.encode("ascii", "ignore").decode("ascii").strip()
    if len(ascii_text) > max_length:
        return ascii_text[: max_length - 3] + "..."
    return ascii_text or "VideoFlow notification"


def delete_s3_prefix(bucket: str, prefix: str) -> None:
    if not bucket:
        return

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue
        s3_client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
        )


def delete_job_connections(job_id: str) -> None:
    if not CONNECTIONS_TABLE:
        return

    table = get_connections_table()
    response = table.query(
        IndexName="JobIdIndex",
        KeyConditionExpression="jobId = :jobId",
        ExpressionAttributeValues={":jobId": job_id},
    )

    for item in response.get("Items", []):
        table.delete_item(Key={"connectionId": item["connectionId"]})


def delete_job_assets(job: dict) -> None:
    job_id = job["jobId"]
    keys_to_delete: set[tuple[str, str]] = set()

    if UPLOAD_BUCKET and job.get("s3Key"):
        keys_to_delete.add((UPLOAD_BUCKET, job["s3Key"]))
    if PROCESSED_BUCKET and job.get("thumbnailKey"):
        keys_to_delete.add((PROCESSED_BUCKET, job["thumbnailKey"]))
    if PROCESSED_BUCKET and job.get("outputs"):
        for key in job["outputs"].values():
            keys_to_delete.add((PROCESSED_BUCKET, key))

    for bucket, key in keys_to_delete:
        try:
            s3_client.delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            print(f"Failed to delete s3://{bucket}/{key}: {exc}")

    try:
        delete_s3_prefix(UPLOAD_BUCKET, f"uploads/{job_id}/")
        delete_s3_prefix(PROCESSED_BUCKET, f"processed/{job_id}/")
    except ClientError as exc:
        print(f"Failed to delete S3 prefix for job {job_id}: {exc}")

    try:
        delete_job_connections(job_id)
    except ClientError as exc:
        print(f"Failed to delete WebSocket connections for job {job_id}: {exc}")


def publish_sns_notification(job: dict) -> None:
    if not NOTIFICATIONS_TOPIC_ARN:
        return

    filename = job.get("filename", job["jobId"])
    subject = sanitize_sns_subject(f"VideoFlow - traitement termine ({filename})")

    try:
        sns_client.publish(
            TopicArn=NOTIFICATIONS_TOPIC_ARN,
            Subject=subject,
            Message=json.dumps(
                {
                    "jobId": job["jobId"],
                    "status": job.get("status"),
                    "filename": job.get("filename"),
                    "metadata": job.get("metadata"),
                    "completedAt": job.get("completedAt"),
                },
                default=decimal_default,
            ),
        )
    except ClientError as exc:
        print(f"SNS publish failed for job {job['jobId']}: {exc}")


def notify_job_subscribers(job_id: str, payload: dict) -> None:
    if not CONNECTIONS_TABLE or not WEBSOCKET_ENDPOINT:
        return

    table = get_connections_table()
    client = get_apigw_management()
    if client is None:
        return

    response = table.query(
        IndexName="JobIdIndex",
        KeyConditionExpression="jobId = :jobId",
        ExpressionAttributeValues={":jobId": job_id},
    )

    message = json.dumps({"type": "job_update", "job": payload}, default=decimal_default)

    for item in response.get("Items", []):
        connection_id = item["connectionId"]
        try:
            client.post_to_connection(ConnectionId=connection_id, Data=message.encode("utf-8"))
        except ClientError as error:
            if error.response["Error"]["Code"] == "GoneException":
                table.delete_item(Key={"connectionId": connection_id})
