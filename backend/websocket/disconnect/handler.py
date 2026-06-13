from utils import get_connections_table, ws_response


def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    get_connections_table().delete_item(Key={"connectionId": connection_id})
    return ws_response(200)
