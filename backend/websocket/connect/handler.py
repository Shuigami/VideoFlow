from utils import get_connections_table, now_iso, ws_response


def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    get_connections_table().put_item(
        Item={
            "connectionId": connection_id,
            "connectedAt": now_iso(),
        }
    )
    return ws_response(200, {"message": "connected"})
